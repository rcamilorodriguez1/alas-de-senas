"""Ruta de aprendizaje con estados derivados por `compute_progress` (D3, §8.1)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domain.enums import ProgressStatus
from app.domain.policies.progress import (
    CurriculumLesson,
    CurriculumModule,
    CurriculumNode,
    ProgressFacts,
    ProgressMap,
    compute_progress,
    module_progress_percent,
)
from app.domain.policies.rewards import RewardPolicy
from app.infra.models import Lesson, Module, Node
from app.infra.repositories import curriculum as repo
from app.infra.repositories.curriculum import LessonFacts
from app.schemas.curriculum import (
    LearningPathOut,
    LessonSummaryOut,
    ModuleOut,
    NodeDetailOut,
    NodeSignOut,
    NodeSummaryOut,
)


def _node_not_found() -> AppError:
    return AppError(404, "NODE_NOT_FOUND", "No encontramos este nodo.")


class CurriculumService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.rewards = RewardPolicy()

    def get_learning_path(self, user_id: uuid.UUID) -> LearningPathOut:
        modules = repo.load_curriculum(self.session)
        facts = repo.lesson_facts(self.session, user_id)
        progress = self._progress(modules, facts)
        return LearningPathOut(
            modules=[self._module_out(module, progress, facts) for module in modules]
        )

    def progress_map(self, user_id: uuid.UUID) -> ProgressMap:
        """Estados derivados del usuario (para iniciar y completar lecciones)."""
        modules = repo.load_curriculum(self.session)
        return self._progress(modules, repo.lesson_facts(self.session, user_id))

    def get_node(self, user_id: uuid.UUID, node_id: str) -> NodeDetailOut:
        modules = repo.load_curriculum(self.session)
        module = next((m for m in modules for n in m.nodes if n.id == node_id), None)
        if module is None or not module.published:
            raise _node_not_found()
        node = next(n for n in module.nodes if n.id == node_id)
        facts = repo.lesson_facts(self.session, user_id)
        progress = self._progress(modules, facts)
        signs = repo.node_signs(self.session, node_id)
        return NodeDetailOut(
            id=node.id,
            title=node.title,
            kind=node.kind,
            status=progress.nodes[node.id],
            module_id=module.id,
            module_title=module.title,
            lessons=[self._lesson_out(lesson, progress, facts) for lesson in node.lessons],
            signs=[
                NodeSignOut(
                    slug=sign.id,
                    word=sign.word,
                    poster=sign.poster_path,
                    introduced_in_lesson_id=sign.introduced_in_lesson_id,
                )
                for sign in signs
            ],
        )

    # ---- cálculo ---------------------------------------------------------------------------

    @staticmethod
    def _progress(modules: Sequence[Module], facts: Mapping[str, LessonFacts]) -> ProgressMap:
        curriculum = [
            CurriculumModule(
                id=module.id,
                order=module.order,
                published=module.published,
                nodes=tuple(
                    CurriculumNode(
                        id=node.id,
                        order=node.order,
                        lessons=tuple(
                            CurriculumLesson(id=lesson.id, order=lesson.order, type=lesson.type)
                            for lesson in node.lessons
                        ),
                    )
                    for node in module.nodes
                ),
            )
            for module in modules
        ]
        best = {lid: f.best_score for lid, f in facts.items() if f.best_score is not None}
        return compute_progress(curriculum, ProgressFacts(best_scores=best, passed=_passed(facts)))

    def _module_out(
        self, module: Module, progress: ProgressMap, facts: Mapping[str, LessonFacts]
    ) -> ModuleOut:
        if not module.published:
            nodes = [
                self._node_out(node, progress, facts, coming_soon=True) for node in module.nodes
            ]
            return ModuleOut(
                id=module.id,
                order=module.order,
                title=module.title,
                description=module.description,
                published=False,
                status=ProgressStatus.COMING_SOON,
                progress=0,
                nodes=nodes,
            )
        lesson_ids = [lesson.id for node in module.nodes for lesson in node.lessons]
        percent = module_progress_percent(lesson_ids, _passed(facts))
        return ModuleOut(
            id=module.id,
            order=module.order,
            title=module.title,
            description=module.description,
            published=True,
            status=progress.modules[module.id],
            progress=percent,
            nodes=[self._node_out(node, progress, facts) for node in module.nodes],
        )

    def _node_out(
        self,
        node: Node,
        progress: ProgressMap,
        facts: Mapping[str, LessonFacts],
        *,
        coming_soon: bool = False,
    ) -> NodeSummaryOut:
        return NodeSummaryOut(
            id=node.id,
            order=node.order,
            title=node.title,
            kind=node.kind,
            status=ProgressStatus.COMING_SOON if coming_soon else progress.nodes[node.id],
            lessons=[]
            if coming_soon
            else [self._lesson_out(lesson, progress, facts) for lesson in node.lessons],
        )

    def _lesson_out(
        self, lesson: Lesson, progress: ProgressMap, facts: Mapping[str, LessonFacts]
    ) -> LessonSummaryOut:
        fact = facts.get(lesson.id, _NO_FACTS)
        return LessonSummaryOut(
            id=lesson.id,
            order=lesson.order,
            type=lesson.type,
            title=lesson.title,
            status=progress.lessons[lesson.id],
            best_score=fact.best_score,
            estimated_xp=self.rewards.max_xp(lesson.type, fact.passed),
        )


_NO_FACTS = LessonFacts(best_score=None, passed=False)


def _passed(facts: Mapping[str, LessonFacts]) -> set[str]:
    return {lesson_id for lesson_id, fact in facts.items() if fact.passed}
