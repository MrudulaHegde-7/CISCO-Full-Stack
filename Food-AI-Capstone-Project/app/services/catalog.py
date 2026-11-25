from decimal import Decimal

from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import MenuItem
from app.repositories.protocols import MenuRepository
from app.schemas import ItemCreate, ItemUpdate


class CatalogService:
    def __init__(self, repository: MenuRepository) -> None:
        self.repository = repository

    def search(
        self,
        *,
        category: str | None = None,
        vegetarian: bool | None = None,
        max_price: Decimal | None = None,
        keyword: str | None = None,
        admin: bool = False,
        include_inactive: bool = False,
    ) -> list[MenuItem]:
        return self.repository.search(
            category=category,
            vegetarian=vegetarian,
            max_price=float(max_price) if max_price is not None else None,
            keyword=keyword,
            active_only=not (admin and include_inactive),
        )

    def get(self, item_id: int, *, include_inactive: bool = False) -> MenuItem:
        item = self.repository.get(item_id)
        if item is None or (not include_inactive and not item.active):
            raise NotFoundError("Menu item not found")
        return item

    def create(self, data: ItemCreate) -> MenuItem:
        return self.repository.add(MenuItem(**data.model_dump()))

    def update(self, item_id: int, data: ItemUpdate) -> MenuItem:
        item = self.get(item_id, include_inactive=True)
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(item, field, value)
        return item

    def delete(self, item_id: int) -> str:
        item = self.get(item_id, include_inactive=True)
        return self.repository.delete_or_archive(item)