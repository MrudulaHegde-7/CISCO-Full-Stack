from fastapi import Depends, FastAPI, status

from CommerceHub.models import OrderRequest, OrderResponse
from CommerceHub.repository import InMemoryOrderRepository
from CommerceHub.service import OrderService

app = FastAPI(title="CommerceHub Order Management API")

repository = InMemoryOrderRepository()
service = OrderService(repository)


def get_order_service() -> OrderService:
    return service


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_order(
    order: OrderRequest,
    order_service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    return order_service.create_order(order)


@app.get("/orders", response_model=list[OrderResponse])
def list_orders(
    order_service: OrderService = Depends(get_order_service),
) -> list[OrderResponse]:
    return order_service.list_orders()