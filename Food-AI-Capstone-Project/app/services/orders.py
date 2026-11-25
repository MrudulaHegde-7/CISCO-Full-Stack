import hashlib
import json
from decimal import Decimal

from sqlalchemy.orm import Session

from app.errors import ConflictError, ForbiddenError, NotFoundError
from app.models import MenuItem, Order, OrderLine
from app.repositories.protocols import MenuRepository, OrderRepository
from app.schemas import OrderCreate


class OrderService:
    def __init__(
        self,
        orders: OrderRepository,
        menu: MenuRepository,
        session: Session,
    ) -> None:
        self.orders = orders
        self.menu = menu
        self.session = session

    @staticmethod
    def _fingerprint(data: OrderCreate) -> str:
        payload = sorted(
            ({"item_id": line.item_id, "quantity": line.quantity} for line in data.lines),
            key=lambda line: line["item_id"],
        )
        return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()

    def create(self, user_id: int, data: OrderCreate, idempotency_key: str) -> Order:
        if not idempotency_key or len(idempotency_key) > 120:
            raise ConflictError("A valid Idempotency-Key header is required")

        self.orders.lock_user(user_id)
        fingerprint = self._fingerprint(data)
        prior = self.orders.by_idempotency_key(user_id, idempotency_key)
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                raise ConflictError("This idempotency key was already used for a different order")
            return prior

        quantities: dict[int, int] = {}
        for line in data.lines:
            quantities[line.item_id] = quantities.get(line.item_id, 0) + line.quantity
        if any(quantity > 10 for quantity in quantities.values()):
            raise ConflictError("Combined quantity for an item cannot exceed 10")

        items = self.menu.get_many_for_update(sorted(quantities))
        by_id = {item.id: item for item in items}
        if len(by_id) != len(quantities):
            raise NotFoundError("One or more menu items were not found")
        for item_id, quantity in quantities.items():
            item = by_id[item_id]
            if not item.active:
                raise ConflictError(f"{item.title} is no longer available")
            if item.capacity < quantity:
                raise ConflictError(f"Insufficient availability for {item.title}")

        total = sum(
            (by_id[line.item_id].price * line.quantity for line in data.lines),
            start=Decimal("0.00"),
        ).quantize(Decimal("0.01"))
        order = Order(
            user_id=user_id,
            status="CONFIRMED",
            total=total,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
        self.session.add(order)
        self.session.flush()
        for line in data.lines:
            item = by_id[line.item_id]
            item.capacity -= line.quantity
            order.lines.append(
                OrderLine(
                    item_id=item.id,
                    title_snapshot=item.title,
                    quantity=line.quantity,
                    unit_price=item.price,
                )
            )
        self.session.flush()
        return order

    def get(self, order_id: int, user_id: int, *, admin: bool = False) -> Order:
        order = self.orders.get(order_id)
        if order is None or (not admin and order.user_id != user_id):
            raise NotFoundError("Order not found")
        return order

    def list_for_user(self, user_id: int) -> list[Order]:
        return self.orders.list_for_user(user_id)

    def list_all(self) -> list[Order]:
        return self.orders.list_all()

    def cancel(self, order_id: int, user_id: int) -> Order:
        order = self.orders.get(order_id, for_update=True)
        if order is None or order.user_id != user_id:
            raise NotFoundError("Order not found")
        if order.status != "CONFIRMED":
            raise ConflictError("Orders can only be cancelled before preparation begins")

        item_ids = sorted({line.item_id for line in order.lines})
        items = {item.id: item for item in self.menu.get_many_for_update(item_ids)}
        for line in order.lines:
            item = items.get(line.item_id)
            if item is not None:
                item.capacity += line.quantity
        order.status = "CANCELLED"
        self.session.flush()
        return order

    def set_status(self, order_id: int, status: str) -> Order:
        order = self.orders.get(order_id, for_update=True)
        if order is None:
            raise NotFoundError("Order not found")
        allowed = {"CONFIRMED": "PREPARING", "PREPARING": "READY", "READY": "COMPLETED"}
        if allowed.get(order.status) != status:
            raise ConflictError(f"Status transition {order.status} to {status} is not allowed")
        order.status = status
        self.session.flush()
        return order