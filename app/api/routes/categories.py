"""Rotas de categorias de negocio (secao 7 e 39)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.dependencies.db import get_db_session
from app.database.models import Category
from app.schemas.api.categories import CategoryCreateRequest, CategoryResponse

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(session: Session = Depends(get_db_session)) -> list[CategoryResponse]:
    categories = session.exec(select(Category).order_by(Category.name)).all()
    return [CategoryResponse.model_validate(c, from_attributes=True) for c in categories]


@router.post("", response_model=CategoryResponse, status_code=201)
def create_category(
    payload: CategoryCreateRequest, session: Session = Depends(get_db_session)
) -> CategoryResponse:
    category = Category(**payload.model_dump())
    session.add(category)
    session.commit()
    session.refresh(category)
    return CategoryResponse.model_validate(category, from_attributes=True)
