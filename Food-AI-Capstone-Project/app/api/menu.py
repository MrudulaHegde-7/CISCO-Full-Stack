from fastapi import APIRouter, Depends, Query, Response, status
from app.api.dependencies import get_catalog_service
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
    user: User | None = Depends(get_optional_user),
    service: CatalogService = Depends(get_catalog_service),
) -> list[ItemResponse]:
    return service.search(
        category=category,
        vegetarian=vegetarian,
        max_price=max_price,
        keyword=keyword,
        admin=user is not None and user.role == "ADMIN",
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
    service: CatalogService = Depends(get_catalog_service),
    _admin: User = Depends(require_admin),
) -> ItemResponse:
    return service.create(data)


@router.put("/{item_id}", response_model=ItemResponse)
def update_menu_item(
    item_id: int,
    data: ItemUpdate,
    service: CatalogService = Depends(get_catalog_service),
    _admin: User = Depends(require_admin),
) -> ItemResponse:
    return service.update(item_id, data)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def disable_menu_item(
    item_id: int,
    service: CatalogService = Depends(get_catalog_service),
    _admin: User = Depends(require_admin),
) -> Response:
    service.disable(item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)