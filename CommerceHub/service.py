from CommerceHub.models import OrderRequest, OrderResponse
from CommerceHub.repository import OrderRepository


class OrderService:
    def __init__(self, repository: OrderRepository) -> None:
        self.repository = repository

    def calculate_total(self, order: OrderRequest) -> float:
        return round(
            sum(item.quantity * item.unit_price for item in order.items),
            2,
        )

    def create_order(self, order: OrderRequest) -> OrderResponse:
        total = self.calculate_total(order)
        return self.repository.save(order, total)

    def list_orders(self) -> list[OrderResponse]:
        return self.repository.list_all()