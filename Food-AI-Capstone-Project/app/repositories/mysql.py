from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.models import MenuItem, Order, User


class SQLAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def by_username(self, username: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == username))

    def by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user


class SQLAlchemyMenuRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(
        self,
        *,
        category: str | None = None,
        vegetarian: bool | None = None,
        max_price: float | None = None,
        keyword: str | None = None,
        active_only: bool = True,
    ) -> list[MenuItem]:
        query: Select[tuple[MenuItem]] = select(MenuItem)
        if active_only:
            query = query.where(MenuItem.active.is_(True))
        if category:
            query = query.where(MenuItem.category.ilike(f"%{category.strip()}%"))
        if vegetarian is not None:
            query = query.where(MenuItem.vegetarian.is_(vegetarian))
        if max_price is not None:
            query = query.where(MenuItem.price <= max_price)
        if keyword:
            pattern = f"%{keyword.strip()}%"
            query = query.where(MenuItem.title.ilike(pattern) | MenuItem.description.ilike(pattern))
        return list(self.session.scalars(query.order_by(MenuItem.category, MenuItem.title)))

    def get(self, item_id: int, *, for_update: bool = False) -> MenuItem | None:
        query = select(MenuItem).where(MenuItem.id == item_id)
        if for_update:
            query = query.with_for_update()
        return self.session.scalar(query)

    def get_many_for_update(self, item_ids: list[int]) -> list[MenuItem]:
        if not item_ids:
            return []
        query = (
            select(MenuItem)
            .where(MenuItem.id.in_(item_ids))
            .order_by(MenuItem.id)
            .with_for_update()
        )
        return list(self.session.scalars(query))

    def add(self, item: MenuItem) -> MenuItem:
        self.session.add(item)
        self.session.flush()
        return item


class SQLAlchemyOrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def lock_user(self, user_id: int) -> None:
        self.session.scalar(select(User.id).where(User.id == user_id).with_for_update())

    def by_idempotency_key(self, user_id: int, key: str) -> Order | None:
        query = (
            select(Order)
            .options(selectinload(Order.lines))
            .where(Order.user_id == user_id, Order.idempotency_key == key)
        )
        return self.session.scalar(query)

    def get(self, order_id: int, *, for_update: bool = False) -> Order | None:
        query = select(Order).options(selectinload(Order.lines)).where(Order.id == order_id)
        if for_update:
            query = query.with_for_update()
        return self.session.scalar(query)

    def list_for_user(self, user_id: int) -> list[Order]:
        query = (
            select(Order)
            .options(selectinload(Order.lines))
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
        )
        return list(self.session.scalars(query))

    def list_all(self) -> list[Order]:
        query = select(Order).options(selectinload(Order.lines)).order_by(Order.created_at.desc())
        return list(self.session.scalars(query))