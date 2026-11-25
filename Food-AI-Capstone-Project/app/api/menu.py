from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_catalog_service
from app.db import get_db
from app.models import User
from app.schemas import ItemCreate, ItemResponse, ItemUpdate
from app.security.auth import get_optional_user, require_admin
from app.services.catalog import CatalogService

router = APIRouter(prefix="/api/menu_items", tags=["menu"])


@router.get("", response_model=list[ItemResponse])
def list_menu_items(
    category: str | None = Query(default=None, max_length=80),
    vegetarian: bool | None = None,
    max_price: float | None = Query(default=None, gt=0),
    keyword: str | None = Query(default=None, max_length=120),
    include_inactive: bool = False,
    user: User | None = Depends(get_optional_user),
    service: CatalogService = Depends(get_catalog_service),
) -> list[ItemResponse]:
    return service.search(
        category=category,
        vegetarian=vegetarian,
        max_price=max_price,
        keyword=keyword,
        admin=user is not None and user.role == "ADMIN",
        include_inactive=include_inactive,
    )


@router.get("/{item_id}", response_model=ItemResponse)
def get_menu_item(
    item_id: int,
    service: CatalogService = Depends(get_catalog_service),
) -> ItemResponse:
    return service.get(item_id)


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_menu_item(
    data: ItemCreate,
    session: Session = Depends(get_db),
    service: CatalogService = Depends(get_catalog_service),
    _admin: User = Depends(require_admin),
) -> ItemResponse:
    item = service.create(data)
    session.commit()
    return item


@router.put("/{item_id}", response_model=ItemResponse)
def update_menu_item(
    item_id: int,
    data: ItemUpdate,
    session: Session = Depends(get_db),
    service: CatalogService = Depends(get_catalog_service),
    _admin: User = Depends(require_admin),
) -> ItemResponse:
    item = service.update(item_id, data)
    session.commit()
    return item


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a menu item or archive it when order history references it",
)
def delete_menu_item(
    item_id: int,
    session: Session = Depends(get_db),
    service: CatalogService = Depends(get_catalog_service),
    _admin: User = Depends(require_admin),
) -> Response:
    removal_mode = service.delete(item_id)
    session.commit()
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={"X-Menu-Item-Removal": removal_mode},
    )