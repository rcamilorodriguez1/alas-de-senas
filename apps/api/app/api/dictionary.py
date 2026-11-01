"""Rutas del diccionario (§8.2). Buscar y ver fichas no requiere sesión; los favoritos sí."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import ClockDep, CurrentUser, DbSession, OptionalUser
from app.schemas.dictionary import CategoryOut, SignCardOut, SignDetailOut, SignSearchOut
from app.services.dictionary_service import DictionaryService

router = APIRouter(prefix="/dictionary", tags=["dictionary"])


def get_dictionary_service(db: DbSession, clock: ClockDep) -> DictionaryService:
    return DictionaryService(db, clock)


DictionaryServiceDep = Annotated[DictionaryService, Depends(get_dictionary_service)]


@router.get("/signs", response_model=SignSearchOut)
def search(
    service: DictionaryServiceDep,
    q: Annotated[str, Query(max_length=80)] = "",
    category: Annotated[str | None, Query(max_length=32)] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
) -> SignSearchOut:
    return service.search(q, category, page)


@router.get("/signs/{slug}", response_model=SignDetailOut)
def get_sign(slug: str, user: OptionalUser, service: DictionaryServiceDep) -> SignDetailOut:
    return service.get_sign(user, slug)


@router.get("/categories", response_model=list[CategoryOut])
def categories(service: DictionaryServiceDep) -> list[CategoryOut]:
    return service.get_categories()


@router.get("/favorites", response_model=list[SignCardOut])
def favorites(user: CurrentUser, service: DictionaryServiceDep) -> list[SignCardOut]:
    return service.list_favorites(user)


@router.post("/favorites/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def add_favorite(
    slug: str, user: CurrentUser, service: DictionaryServiceDep, db: DbSession
) -> Response:
    service.add_favorite(user, slug)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/favorites/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    slug: str, user: CurrentUser, service: DictionaryServiceDep, db: DbSession
) -> Response:
    service.remove_favorite(user, slug)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
