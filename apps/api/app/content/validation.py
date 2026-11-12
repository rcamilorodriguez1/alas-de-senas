"""`alas content check`: todas las validaciones de §6.6 y el reporte."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from app.content.csv_reader import SignRow
from app.content.errors import ContentError
from app.content.images import MIN_HEIGHT, image_height
from app.content.loader import CATEGORIES, ContentBundle, load_content, to_sign_specs
from app.content.media import Manifest, load_manifest
from app.content.raw_files import scan_raw
from app.domain.content.generator import generate_content, split_counts, split_word_into_letters
from app.domain.content.models import GenerationError, NodeSpec
from app.domain.enums import Motion, NodeKind
from app.domain.text import levenshtein

NODE_SIZE: dict[str, tuple[int, int]] = {
    "STANDARD": (5, 9),
    "NUMBERS": (5, 10),
    "ALPHABET": (12, 16),
}
MIN_SCORED_EXERCISES = 4
MIN_SPELLING_WORDS = 6
MIN_SPELLING_WORDS_L2 = 4
MAX_VIDEO_SECONDS = 8

ALPHABET_CATEGORY = "alfabeto"
# Números: motion opcional; los estáticos pueden reconocerse con la cámara (D-019).
NUMBERS_CATEGORY = "numeros"
NONE_LABEL = "NINGUNA"
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
CATEGORY_SUGGESTION_DISTANCE = 2
REQUIRED_TEXT = ("word", "meaning", "usage_example")
DEFAULT_LABELS = Path("models") / "lsc-alfabeto" / "labels.json"  # relativo a public/
DATASET_MAPPING = "dataset-mapping.csv"  # señas de datasets externos → slugs (anexo A.7)
MAPPING_HEADER = ["fuente", "etiqueta_fuente", "slug"]
DATASETS = "datasets.csv"  # fuente, licencia, enlace y cita de cada dataset externo (D-044)
DATASETS_HEADER = ["fuente", "licencia", "enlace", "cita"]
CAMERA_EQUIVALENCES = "camera-equivalences.csv"  # señas con la misma forma de mano (D-027)
EQUIVALENCES_HEADER = ["slug", "equivalente", "nota"]


@dataclass(slots=True)
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Por módulo publicado: (señas con video/imágenes reales, señas de relleno)
    media_by_module: dict[str, tuple[int, int]] = field(default_factory=dict)
    missing_how_to: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        """Texto en español para la terminal: resumen por módulo, advertencias y errores."""
        lines = ["Reporte de contenido", "", "Videos por módulo publicado (reales / de relleno):"]
        for module_id, (real, placeholder) in sorted(self.media_by_module.items()):
            lines.append(f"  {module_id}: {real} reales · {placeholder} de relleno")
        if self.missing_how_to:
            lines += [
                "",
                f"Señas sin descripción «cómo se hace» ({len(self.missing_how_to)}): "
                + ", ".join(self.missing_how_to),
            ]
        if self.warnings:
            lines += ["", f"Advertencias ({len(self.warnings)}):"]
            lines += [f"  ⚠ {w}" for w in self.warnings]
        lines.append("")
        if self.errors:
            lines.append(f"Errores ({len(self.errors)}):")
            lines += [f"  ✗ {e}" for e in self.errors]
        else:
            lines.append("✓ Sin errores.")
        return "\n".join(lines)


def check_content(
    content_dir: Path,
    media_dir: Path,
    *,
    skip_raw: bool = False,
    labels_path: Path | None = None,
) -> Report:
    """Valida `content_dir` (y `content_dir/videos/raw` salvo `skip_raw`) contra §6.6.

    Nunca lanza por errores de contenido: los acumula en `Report.errors` (los ContentError de
    lectura también se reportan como un error). Reglas: ver la tabla de §6.6 y D-007/D-008
    (las mismas que usa el generador: un GenerationError se reporta como error).
    `labels_path`: `labels.json` del modelo del alfabeto (lista de slugs); si existe se valida.
    """
    report = Report()
    try:
        bundle = load_content(content_dir)
    except ContentError as exc:
        report.errors.append(str(exc))
        return report

    nodes = {node.id: node for record in bundle.modules for node in record.spec.nodes}
    published_nodes = [
        node
        for record in sorted(bundle.modules, key=lambda r: r.spec.order)
        if record.spec.published
        for node in sorted(record.spec.nodes, key=lambda n: n.order)
    ]
    _check_rows(bundle.signs, nodes, report)
    _check_node_sizes(bundle.signs, nodes, published_nodes, report)
    _check_motion(bundle.signs, report)
    _check_labels(bundle.signs, labels_path or media_dir.parent / DEFAULT_LABELS, report)
    sources = _check_dataset_mapping(bundle.signs, content_dir / DATASET_MAPPING, report)
    _check_datasets(sources, content_dir / DATASETS, report)
    _check_equivalences(bundle.signs, content_dir / CAMERA_EQUIVALENCES, report)
    _check_conversations(bundle, published_nodes, report)
    _check_spelling(bundle, published_nodes, report)
    _check_intro(bundle, report)
    if not report.errors:
        _check_generation(bundle, report)
    _check_manifest(bundle, media_dir, report)
    report.missing_how_to = [row.slug for row in bundle.signs if not row.how_to]
    if not skip_raw:
        _check_raw(content_dir, bundle, report)
    return report


# ---------- Filas del CSV -----------------------------------------------------------------------


def _check_rows(rows: Sequence[SignRow], nodes: Mapping[str, NodeSpec], report: Report) -> None:
    lines: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        lines[row.slug].append(row.line)
    for slug, found in lines.items():
        if len(found) > 1:
            listed = " y ".join(str(n) for n in found)
            report.errors.append(f'Slug repetido: "{slug}" (filas {listed}).')

    categories = [cid for cid, _ in CATEGORIES]
    for row in rows:
        if not SLUG_PATTERN.match(row.slug):
            report.errors.append(
                f'signs.csv fila {row.line}: el slug "{row.slug}" no es válido: usa minúsculas '
                "sin tildes, números y guiones (sin espacios ni «_»)."
            )
        if row.category not in categories:
            report.errors.append(_unknown_category(row.category, categories))
        if row.node is not None and row.node not in nodes:
            report.errors.append(f'{row.slug}: el nodo "{row.node}" no existe en curriculum.json.')
        for column in REQUIRED_TEXT:
            if not getattr(row, column):
                report.errors.append(f"{row.slug} (fila {row.line}): {column} está vacío.")

    by_node_order: dict[tuple[str, int], list[str]] = defaultdict(list)
    for row in rows:
        if row.node is not None:
            by_node_order[(row.node, row.order)].append(row.slug)
    for (node_id, order), slugs in sorted(by_node_order.items()):
        if len(slugs) > 1:
            report.errors.append(f"{node_id}: el order {order} está repetido ({', '.join(slugs)}).")


def _unknown_category(category: str, categories: Sequence[str]) -> str:
    message = f'Categoría "{category}" no existe.'
    best = min(categories, key=lambda c: (levenshtein(category, c), c))
    if levenshtein(category, best) <= CATEGORY_SUGGESTION_DISTANCE:
        message += f' ¿Quisiste decir "{best}"?'
    return message


def _check_node_sizes(
    rows: Sequence[SignRow],
    nodes: Mapping[str, NodeSpec],
    published_nodes: Sequence[NodeSpec],
    report: Report,
) -> None:
    counts = Counter(row.node for row in rows if row.node is not None)
    published = {node.id for node in published_nodes}
    for node_id, node in nodes.items():
        if node_id not in published:
            continue  # los módulos no publicados no generan lecciones (B58)
        minimum, maximum = NODE_SIZE[node.kind.value]
        count = counts.get(node_id, 0)
        if count < minimum:
            report.errors.append(f"{node_id} tiene {count} señas; mínimo {minimum}.")
        elif count > maximum:
            report.errors.append(f"{node_id} tiene {count} señas; máximo {maximum}.")


def _check_motion(rows: Sequence[SignRow], report: Report) -> None:
    valid = {m.value for m in Motion}
    for row in rows:
        if row.category == ALPHABET_CATEGORY:
            if row.motion is None:
                report.errors.append(f"{row.slug}: falta la columna motion (static o dynamic).")
            elif row.motion not in valid:
                report.errors.append(
                    f'{row.slug}: motion "{row.motion}" no es válido (static o dynamic).'
                )
        elif row.category == NUMBERS_CATEGORY:
            if row.motion is not None and row.motion not in valid:
                report.errors.append(
                    f'{row.slug}: motion "{row.motion}" no es válido (static o dynamic).'
                )
        elif row.motion is not None:
            report.errors.append(
                f"{row.slug}: solo las letras y los números llevan motion; déjalo vacío."
            )


def _check_labels(rows: Sequence[SignRow], labels_path: Path, report: Report) -> None:
    if not labels_path.is_file():
        return
    try:
        labels = json.loads(labels_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        report.errors.append(f"{labels_path.name} no es un JSON válido.")
        return
    if not isinstance(labels, list):
        report.errors.append(f"{labels_path.name} debe ser una lista de slugs.")
        return
    by_slug = {row.slug: row for row in rows}
    for label in labels:
        if label == NONE_LABEL:  # clase «sin seña» del modelo (§10.5): no es un slug
            continue
        row = by_slug.get(str(label))
        if row is None:
            report.errors.append(f"El modelo del alfabeto incluye {label}, que no es una seña.")
        elif row.motion == Motion.DYNAMIC.value:
            report.errors.append(
                f"El modelo del alfabeto incluye {label}, que tiene movimiento: el modelo "
                "estático no puede reconocerla."
            )


def _source_key(text: str) -> str:
    """«Buenos Días» y «buenos-dias» son la misma etiqueta (así compara el importador)."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return "-".join("".join(c if c.isalnum() else " " for c in plain).split())


def _check_dataset_mapping(rows: Sequence[SignRow], path: Path, report: Report) -> set[str]:
    """Valida el mapeo y devuelve sus fuentes (cada una debe estar en `datasets.csv`)."""
    if not path.is_file():
        return set()
    lines = [
        (n, line)
        for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1)
        if line.strip() and not line.startswith("#")
    ]
    if not lines or [c.strip() for c in lines[0][1].split(",")] != MAPPING_HEADER:
        report.errors.append(
            f"{DATASET_MAPPING}: la cabecera debe ser «{','.join(MAPPING_HEADER)}»."
        )
        return set()
    slugs = {row.slug for row in rows} | {NONE_LABEL}
    seen: set[tuple[str, str]] = set()
    sources: set[str] = set()
    for n, line in lines[1:]:
        cells = [c.strip() for c in line.split(",")]
        if len(cells) != len(MAPPING_HEADER) or not all(cells):
            report.errors.append(
                f"{DATASET_MAPPING}, línea {n}: se esperaban tres columnas no vacías."
            )
            continue
        source, label, slug = cells
        sources.add(source)
        if slug not in slugs:
            report.errors.append(
                f"{DATASET_MAPPING}, línea {n}: «{slug}» no es una seña de signs.csv."
            )
        key = (source, _source_key(label))
        if key in seen:
            report.errors.append(
                f"{DATASET_MAPPING}, línea {n}: etiqueta «{label}» repetida en {source}."
            )
        seen.add(key)
    return sources


def _check_datasets(sources: set[str], path: Path, report: Report) -> None:
    """`datasets.csv`: cada fuente del mapeo con licencia, enlace y cita (atribución, D-044)."""
    if not path.is_file():
        for source in sorted(sources):
            report.errors.append(
                f"{DATASETS}: falta el archivo; la fuente «{source}» no tiene licencia."
            )
        return
    with path.open(encoding="utf-8-sig", newline="") as handle:
        lines = [
            (n, [cell.strip() for cell in row])
            for n, row in enumerate(csv.reader(handle), start=1)
            if row and any(cell.strip() for cell in row) and not row[0].startswith("#")
        ]
    if not lines or lines[0][1] != DATASETS_HEADER:
        report.errors.append(f"{DATASETS}: la cabecera debe ser «{','.join(DATASETS_HEADER)}».")
        return
    registered: set[str] = set()
    for n, cells in lines[1:]:
        if len(cells) != len(DATASETS_HEADER) or not all(cells):
            report.errors.append(
                f"{DATASETS}, línea {n}: se esperaban cuatro columnas no vacías "
                "(pon la cita entre comillas si tiene comas)."
            )
            continue
        source, _license, link, _citation = cells
        if not link.startswith("https://"):
            report.errors.append(f"{DATASETS}, línea {n}: el enlace debe empezar por https://.")
        if source in registered:
            report.errors.append(f"{DATASETS}, línea {n}: fuente «{source}» repetida.")
        registered.add(source)
    for source in sorted(sources - registered):
        report.errors.append(
            f"{DATASETS}: la fuente «{source}» del mapeo no tiene licencia registrada."
        )


def _data_lines(path: Path) -> list[tuple[int, list[str]]]:
    """Líneas no vacías y sin comentario, con su número; celdas sin espacios alrededor."""
    return [
        (n, [cell.strip() for cell in line.split(",")])
        for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1)
        if line.strip() and not line.startswith("#")
    ]


def _check_equivalences(rows: Sequence[SignRow], path: Path, report: Report) -> None:
    if not path.is_file():
        return
    lines = _data_lines(path)
    name = CAMERA_EQUIVALENCES
    if not lines or lines[0][1] != EQUIVALENCES_HEADER:
        report.errors.append(f"{name}: la cabecera debe ser «{','.join(EQUIVALENCES_HEADER)}».")
        return
    slugs = {row.slug for row in rows}
    seen: set[frozenset[str]] = set()
    for n, cells in lines[1:]:
        # La nota puede tener comas: solo las dos primeras columnas son slugs.
        if len(cells) < len(EQUIVALENCES_HEADER) - 1 or not cells[0] or not cells[1]:
            report.errors.append(f"{name}, línea {n}: faltan los dos slugs.")
            continue
        first, second = cells[0], cells[1]
        for slug in (first, second):
            if slug not in slugs:
                report.errors.append(f"{name}, línea {n}: «{slug}» no es una seña de signs.csv.")
        if first == second:
            report.errors.append(f"{name}, línea {n}: «{first}» es la misma seña.")
        pair = frozenset((first, second))
        if pair in seen:
            report.errors.append(f"{name}, línea {n}: par {first} y {second} repetido.")
        seen.add(pair)


# ---------- Conversaciones y deletreo -----------------------------------------------------------


def _taught_before(
    rows: Sequence[SignRow], published_nodes: Sequence[NodeSpec]
) -> dict[str, tuple[set[str], list[set[str]]]]:
    """Por nodo: (señas de nodos anteriores, [señas del nodo hasta L1, L2, L3/L4])."""
    by_node: dict[str, list[SignRow]] = defaultdict(list)
    for row in rows:
        if row.node is not None:
            by_node[row.node].append(row)
    result: dict[str, tuple[set[str], list[set[str]]]] = {}
    previous: set[str] = set()
    for node in published_nodes:
        own = sorted(by_node.get(node.id, []), key=lambda r: r.order)
        a, b, _ = split_counts(node.kind, len(own))
        upto = [{r.slug for r in own[:a]}, {r.slug for r in own[: a + b]}, {r.slug for r in own}]
        result[node.id] = (set(previous), upto)
        previous |= {r.slug for r in own}
    return result


def _check_conversations(
    bundle: ContentBundle, published_nodes: Sequence[NodeSpec], report: Report
) -> None:
    slugs = {row.slug for row in bundle.signs}
    taught = _taught_before(bundle.signs, published_nodes)
    known_nodes = {node.id for record in bundle.modules for node in record.spec.nodes}
    for node_id, value in bundle.conversations.items():
        if node_id not in known_nodes:
            report.errors.append(
                f'conversations.yaml: el nodo "{node_id}" no existe en curriculum.json.'
            )
            continue
        if node_id not in taught:
            continue
        previous, upto = taught[node_id]
        allowed = previous | upto[2]
        for conversation in value.conversations:
            for turn in conversation.turns:
                options = (turn.answer, *turn.distractors)
                for slug in (turn.prompt, *options):
                    if slug not in slugs:
                        report.errors.append(
                            f"{node_id}: la conversación usa «{slug}», que no existe en signs.csv."
                        )
                    elif slug not in allowed:
                        report.errors.append(
                            f"{node_id}: la conversación usa «{slug}», que no se ha enseñado en "
                            f"{node_id} ni en nodos anteriores."
                        )
                if turn.prompt in options:
                    report.errors.append(
                        f"{node_id}: en la conversación, «{turn.prompt}» no puede aparecer "
                        "entre sus propias opciones."
                    )
                if len(set(options)) != len(options):
                    report.errors.append(
                        f"{node_id}: un turno de «{turn.prompt}» tiene opciones repetidas."
                    )


def _check_spelling(
    bundle: ContentBundle, published_nodes: Sequence[NodeSpec], report: Report
) -> None:
    letters = {row.word: row.slug for row in bundle.signs if row.category == ALPHABET_CATEGORY}
    letter_word = {slug: word for word, slug in letters.items()}
    taught = _taught_before(bundle.signs, published_nodes)
    for node in published_nodes:
        if node.kind is not NodeKind.ALPHABET:
            continue
        words = bundle.conversations.get(node.id)
        spelling = words.spelling if words is not None else ()
        previous, upto = taught[node.id]
        if len(spelling) < MIN_SPELLING_WORDS:
            report.errors.append(
                f"{node.id} tiene {len(spelling)} palabras de deletreo; "
                f"mínimo {MIN_SPELLING_WORDS}."
            )
        valid_l2 = 0
        for word in spelling:
            if word != word.upper():
                report.errors.append(
                    f"{node.id}: la palabra de deletreo «{word}» debe ir en mayúsculas."
                )
                continue
            try:
                parts = split_word_into_letters(word, letters)
            except ValueError:
                report.errors.append(
                    f"{node.id}: «{word}» tiene caracteres que no son letras del alfabeto."
                )
                continue
            missing = [p for p in parts if p not in previous | upto[2]]
            if missing:
                report.errors.append(
                    f"«{word}» usa la letra {letter_word[missing[0]]}, que aún no se ha enseñado "
                    f"en {node.id}-L4."
                )
            elif all(p in previous | upto[1] for p in parts):
                valid_l2 += 1
        if spelling and valid_l2 < MIN_SPELLING_WORDS_L2:
            report.errors.append(
                f"{node.id} tiene {valid_l2} palabras de deletreo válidas para L2; mínimo "
                f"{MIN_SPELLING_WORDS_L2}."
            )


def _check_intro(bundle: ContentBundle, report: Report) -> None:
    slugs = {row.slug for row in bundle.signs}
    for where, values in (("cards", bundle.intro.cards), ("quiz", bundle.intro.quiz)):
        for slug in values:
            if slug not in slugs:
                report.errors.append(f"intro.json ({where}): «{slug}» no existe en signs.csv.")


def _check_generation(bundle: ContentBundle, report: Report) -> None:
    try:
        content = generate_content(
            [record.spec for record in bundle.modules],
            to_sign_specs(bundle.signs),
            bundle.conversations,
        )
    except (GenerationError, ValidationError) as exc:
        report.errors.append(str(exc))
        return
    scored = Counter(e.lesson_id for e in content.exercises if e.scored)
    for lesson in content.lessons:
        count = scored.get(lesson.id, 0)
        if count < MIN_SCORED_EXERCISES:
            report.errors.append(
                f"{lesson.id} tiene {count} ejercicios con puntaje; mínimo {MIN_SCORED_EXERCISES}."
            )


# ---------- Medios ------------------------------------------------------------------------------


def _check_manifest(bundle: ContentBundle, media_dir: Path, report: Report) -> None:
    try:
        manifest = load_manifest(media_dir)
    except (ValidationError, ValueError, OSError):
        report.errors.append(
            "media/manifest.json está dañado. Ejecuta alas content all para regenerarlo."
        )
        manifest = Manifest()
    module_of = {
        node.id: record.spec.id
        for record in bundle.modules
        if record.spec.published
        for node in record.spec.nodes
    }
    counts: dict[str, list[int]] = {mid: [0, 0] for mid in module_of.values()}
    for row in bundle.signs:
        entry = manifest.signs.get(row.slug)
        if entry is None:
            report.errors.append(f"Falta el video de «{row.slug}». Ejecuta alas content all.")
            continue
        for kind, url in (("video", entry.video), ("póster", entry.poster)):
            if not (media_dir / url.removeprefix("/media/")).is_file():
                report.errors.append(
                    f"No existe el {kind} de «{row.slug}» ({url}). Ejecuta alas content all."
                )
        module_id = module_of.get(row.node or "")
        if module_id is not None:
            counts[module_id][1 if entry.placeholder else 0] += 1
        if entry.placeholder:
            report.warnings.append(f"«{row.slug}» usa un video de relleno.")
        if entry.duration > MAX_VIDEO_SECONDS:
            report.warnings.append(
                f"«{row.slug}» dura {entry.duration:.1f} s; "
                f"máximo recomendado {MAX_VIDEO_SECONDS} s."
            )
        if entry.source == "images" and not row.how_to:
            report.warnings.append(
                f"IMPORTANTE: «{row.slug}» se muestra con imágenes y no tiene «cómo se hace»: "
                "sin movimiento visible, la descripción escrita es la que lo explica."
            )
    report.media_by_module = {mid: (real, fake) for mid, (real, fake) in counts.items()}


def _check_raw(content_dir: Path, bundle: ContentBundle, report: Report) -> None:
    scan = scan_raw(content_dir / "videos" / "raw", [row.slug for row in bundle.signs])
    report.errors.extend(scan.errors)
    report.warnings.extend(scan.warnings)
    for asset in scan.assets.values():
        if asset.kind != "images":
            continue
        for path in asset.paths:
            try:
                height = image_height(path)
            except OSError:
                report.errors.append(f"raw/{path.name} no es una imagen válida.")
                continue
            if height < MIN_HEIGHT:
                report.warnings.append(
                    f"raw/{path.name} mide {height} px de alto "
                    f"(mínimo {MIN_HEIGHT}): se verá borrosa."
                )
