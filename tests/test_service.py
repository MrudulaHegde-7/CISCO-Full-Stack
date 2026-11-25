from CommerceHub.models import OrderItem, OrderRequest
from CommerceHub.repository import InMemoryOrderRepository
from CommerceHub.service import OrderService


def make_sample_order() -> OrderRequest:
    return OrderRequest(
        customer_name="Anu",
        items=[
            OrderItem(name="Notebook", quantity=2, unit_price=50),
            OrderItem(name="Pen", quantity=1, unit_price=20),
        ],
    )


def test_calculate_total() -> None:
    service = OrderService(InMemoryOrderRepository())

    assert service.calculate_total(make_sample_order()) == 120.0


def test_created_order_can_be_listed() -> None:
    service = OrderService(InMemoryOrderRepository())
    order = service.create_order(make_sample_order())

    assert service.list_orders() == [order]