from typing import Annotated

from fastapi import APIRouter, Depends, Header, status

from app.api.dependencies import get_order_service
from app.models import User
from app.schemas import OrderCreate, OrderResponse, OrderStatusUpdate
from app.security.auth import get_current_user, require_admin
from app.services.orders import OrderService

router = APIRouter(prefix="/api", tags=["orders"])


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderCreate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=120)],
    user: User = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    return service.create(user.id, data, idempotency_key)


@router.get("/orders", response_model=list[OrderResponse])
def list_orders(
    user: User = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> list[OrderResponse]:
    return service.list_all() if user.role == "ADMIN" else service.list_for_user(user.id)


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    user: User = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    return service.get(order_id, user.id, admin=user.role == "ADMIN")


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: int,
    user: User = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    return service.cancel(order_id, user.id)


@router.patch("/admin/orders/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    service: OrderService = Depends(get_order_service),
    _admin: User = Depends(require_admin),
) -> OrderResponse:
    return service.set_status(order_id, data.status)