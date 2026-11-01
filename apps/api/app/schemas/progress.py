"""Esquemas del seguimiento del progreso (§8.2, R6.1 a R6.3)."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.schemas.common import ApiModel


class ModuleProgressOut(ApiModel):
    id: str
    title: str
    order: int
    percent: int


class ProgressSummaryOut(ApiModel):
    percent: int
    modules: list[ModuleProgressOut]
    total_xp: int
    streak: int
    signs_learned: int


class HistoryItemOut(ApiModel):
    session_id: uuid.UUID
    lesson_id: str
    lesson_title: str
    node_title: str
    completed_at: datetime
    score: int
    passed: bool
    xp_earned: int


class HistoryPageOut(ApiModel):
    items: list[HistoryItemOut]
    page: int
    page_size: int
    total: int


class NodeUnitOut(ApiModel):
    id: str
    title: str
    order: int
    average_score: int | None
    accuracy: int | None


class ModuleUnitOut(ApiModel):
    id: str
    title: str
    order: int
    average_score: int | None
    accuracy: int | None
    nodes: list[NodeUnitOut]


class UnitsOut(ApiModel):
    modules: list[ModuleUnitOut]
