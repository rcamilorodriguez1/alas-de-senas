import { Lock } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import { AppLayout } from "../../components/layout/AppLayout";
import { StatsPanel } from "../gamification/StatsPanel";
import { useLearningPath, type LearningModule, type LearningNode } from "./learn-api";
import { LessonPopover } from "./LessonPopover";
import { LESSON_STATUS_TEXT, NODE_STATUS_TEXT, STATUS_STYLE } from "./status";

/** El nodo con la lección disponible actual aparece desplegado al cargar. */
function currentNodeId(modules: LearningModule[]): string | null {
  for (const module of modules) {
    for (const node of module.nodes) {
      if (node.lessons.some((lesson) => lesson.status === "AVAILABLE")) return node.id;
    }
  }
  return null;
}

function StatusIcon({ status }: { status: LearningNode["status"] }) {
  if (status === "LOCKED" || status === "COMING_SOON") {
    return <Lock aria-hidden="true" size={18} />;
  }
  return <span aria-hidden="true">{status === "GOLDEN" ? "⭐" : status === "COMPLETED" ? "✔" : "▶"}</span>;
}

interface PopoverState {
  openLesson: string | null;
  onOpen: (lessonId: string | null) => void;
}

function NodeItem({
  node,
  index,
  expanded,
  onToggle,
  popover,
}: {
  node: LearningNode;
  index: number;
  expanded: boolean;
  onToggle: () => void;
  popover: PopoverState;
}) {
  const triggers = useRef(new Map<string, HTMLButtonElement>());
  const { openLesson, onOpen } = popover;
  const close = useCallback(() => {
    const trigger = openLesson ? triggers.current.get(openLesson) : undefined;
    onOpen(null);
    trigger?.focus(); // el foco vuelve al botón que abrió el diálogo
  }, [openLesson, onOpen]);
  const status = NODE_STATUS_TEXT[node.status];
  const side = index % 2 === 0 ? "self-start ml-8" : "self-end mr-8"; // zigzag
  const selected = node.lessons.find((lesson) => lesson.id === openLesson);
  return (
    <li className={`flex flex-col items-center ${side}`}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className={`flex items-center gap-2 rounded-2xl border-b-4 px-5 py-3 font-display font-bold shadow ${STATUS_STYLE[node.status]}`}
      >
        <StatusIcon status={node.status} />
        <span>
          Nodo {node.order} · {node.title}
          <span className="block text-sm font-semibold">{status}</span>
        </span>
      </button>
      {expanded && (
        <div className="mt-3 flex flex-col items-center">
          <ol className="flex gap-2">
            {node.lessons.map((lesson) => (
              <li key={lesson.id}>
                <button
                  type="button"
                  ref={(element) => {
                    if (element) triggers.current.set(lesson.id, element);
                    else triggers.current.delete(lesson.id);
                  }}
                  aria-expanded={openLesson === lesson.id}
                  aria-controls={openLesson === lesson.id ? `popover-${lesson.id}` : undefined}
                  onClick={() => onOpen(openLesson === lesson.id ? null : lesson.id)}
                  className={`flex flex-col items-center rounded-full border-b-4 px-3 py-2 text-sm font-bold ${STATUS_STYLE[lesson.status]}`}
                >
                  <span className="flex items-center gap-1">
                    {lesson.status === "LOCKED" && <Lock aria-hidden="true" size={14} />}
                    {lesson.order} · {lesson.title}
                  </span>
                  <span className="text-xs font-semibold">{LESSON_STATUS_TEXT[lesson.status]}</span>
                </button>
              </li>
            ))}
          </ol>
          {selected && (
            <LessonPopover key={selected.id} lesson={selected} id={`popover-${selected.id}`} onClose={close} />
          )}
        </div>
      )}
    </li>
  );
}

function ModuleSection({
  module,
  expanded,
  onToggle,
  popover,
}: {
  module: LearningModule;
  expanded: Set<string>;
  onToggle: (nodeId: string) => void;
  popover: PopoverState;
}) {
  const comingSoon = module.status === "COMING_SOON";
  return (
    <section className="mb-10" aria-labelledby={`module-${module.id}`}>
      <div className="rounded-2xl bg-white p-5 shadow">
        <div className="flex items-center justify-between gap-4">
          <h2 id={`module-${module.id}`} className="font-display text-xl font-extrabold">
            Módulo {module.order} · {module.title}
          </h2>
          {comingSoon && (
            <span className="rounded-full bg-violet-100 px-3 py-1 text-sm font-bold text-violet-800">
              Próximamente
            </span>
          )}
          {module.status === "LOCKED" && (
            <span className="flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-sm font-bold text-[#45606A]">
              <Lock aria-hidden="true" size={14} />
              Bloqueado
            </span>
          )}
        </div>
        <p className="text-[#45606A]">{module.description}</p>
        {module.status === "LOCKED" && (
          <p className="text-sm text-[#45606A]">Completa el módulo anterior para desbloquearlo.</p>
        )}
        {!comingSoon && (
          <div className="mt-3 flex items-center gap-3">
            <div
              role="progressbar"
              aria-valuenow={module.progress}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`Avance del módulo ${module.order}`}
              className="h-3 flex-1 overflow-hidden rounded-full bg-slate-200"
            >
              <div className="h-full bg-[#06B6D4]" style={{ width: `${module.progress}%` }} />
            </div>
            <span className="font-semibold">{module.progress} %</span>
          </div>
        )}
      </div>
      {!comingSoon && (
        <ol className="mt-6 flex flex-col gap-6">
          {module.nodes.map((node, index) => (
            <NodeItem
              key={node.id}
              node={node}
              index={index}
              expanded={expanded.has(node.id)}
              onToggle={() => onToggle(node.id)}
              popover={popover}
            />
          ))}
        </ol>
      )}
    </section>
  );
}

function LearningPathView({ modules }: { modules: LearningModule[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    const current = currentNodeId(modules);
    return new Set(current ? [current] : []);
  });
  // Un solo popover abierto en toda la ruta.
  const [openLesson, setOpenLesson] = useState<string | null>(null);
  const popover = useMemo(() => ({ openLesson, onOpen: setOpenLesson }), [openLesson]);
  const toggle = (nodeId: string) =>
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  return (
    <>
      {modules.map((module) => (
        <ModuleSection
          key={module.id}
          module={module}
          expanded={expanded}
          onToggle={toggle}
          popover={popover}
        />
      ))}
    </>
  );
}

export function LearnPage() {
  const { data, isPending, isError, refetch } = useLearningPath();
  return (
    <AppLayout aside={<StatsPanel />}>
      <h1 className="sr-only">Ruta de aprendizaje</h1>
      {isPending && <p role="status">Cargando tu ruta…</p>}
      {isError && (
        <div role="alert" className="rounded-2xl bg-red-50 p-4 text-red-800">
          <p>No pudimos cargar tu ruta.</p>
          <button
            type="button"
            onClick={() => void refetch()}
            className="mt-2 rounded-xl border border-red-300 px-3 py-1.5 font-semibold"
          >
            Reintentar
          </button>
        </div>
      )}
      {data && <LearningPathView modules={data.modules} />}
    </AppLayout>
  );
}
