from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories.mysql import SQLAlchemyMenuRepository, SQLAlchemyOrderRepository
from app.services.catalog import CatalogService
from app.services.orders import OrderService


def get_catalog_service(session: Session = Depends(get_db)) -> CatalogService:
    return CatalogService(SQLAlchemyMenuRepository(session))


def get_order_service(session: Session = Depends(get_db)) -> OrderService:
    return OrderService(
        SQLAlchemyOrderRepository(session),
        SQLAlchemyMenuRepository(session),
        session,
    )