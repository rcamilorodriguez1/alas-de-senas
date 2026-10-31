"""Rutas de la ruta de aprendizaje (§8.2). Solo validan, delegan y responden."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession
from app.schemas.curriculum import LearningPathOut, NodeDetailOut
from app.services.curriculum_service import CurriculumService

router = APIRouter(tags=["curriculum"])


def get_curriculum_service(db: DbSession) -> CurriculumService:
    return CurriculumService(db)


CurriculumServiceDep = Annotated[CurriculumService, Depends(get_curriculum_service)]


@router.get("/learning-path", response_model=LearningPathOut)
def learning_path(user: CurrentUser, service: CurriculumServiceDep) -> LearningPathOut:
    return service.get_learning_path(user.id)


@router.get("/nodes/{node_id}", response_model=NodeDetailOut)
def node_detail(node_id: str, user: CurrentUser, service: CurriculumServiceDep) -> NodeDetailOut:
    return service.get_node(user.id, node_id)
