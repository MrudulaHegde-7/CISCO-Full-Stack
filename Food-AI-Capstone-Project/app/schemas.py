from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ItemCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    category: str = Field(min_length=2, max_length=80)
    vegetarian: bool
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    capacity: int = Field(ge=0)
    description: str = Field(default="", max_length=500)
    image_url: str = Field(default="", max_length=500)
    declared_allergens: str = Field(default="Not specified", max_length=500)


class ItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=120)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    vegetarian: bool | None = None
    price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    capacity: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=500)
    image_url: str | None = Field(default=None, max_length=500)
    declared_allergens: str | None = Field(default=None, max_length=500)
    active: bool | None = None


class ItemResponse(ORMModel):
    id: int
    title: str
    category: str
    vegetarian: bool
    price: Decimal
    capacity: int
    description: str
    image_url: str
    declared_allergens: str
    active: bool


class OrderLineCreate(BaseModel):
    item_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=10)


class OrderCreate(BaseModel):
    lines: list[OrderLineCreate] = Field(min_length=1)


class OrderLineResponse(ORMModel):
    item_id: int
    title_snapshot: str
    quantity: int
    unit_price: Decimal


class OrderResponse(ORMModel):
    id: int
    status: str
    total: Decimal
    created_at: datetime
    lines: list[OrderLineResponse]


class OrderStatusUpdate(BaseModel):
    status: Literal["PREPARING", "READY", "COMPLETED"]


class ChatSessionCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=160)


class ChatSessionResponse(ORMModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class Citation(BaseModel):
    filename: str
    page: int | None = None
    section: str | None = None
    chunk_id: str


class PendingActionResponse(BaseModel):
    id: int
    action: str
    summary: str
    expires_at: datetime


class ChatMessageResponse(ORMModel):
    id: int
    seq_no: int
    role: str
    content: str
    mode: str | None
    metadata_json: dict
    created_at: datetime


class ChatReply(BaseModel):
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    mode: Literal["GENERAL", "RAG", "AGENT", "MIXED"]
    citations: list[Citation] = Field(default_factory=list)
    pending_action: PendingActionResponse | None = None


class ActionDecision(BaseModel):
    confirm: bool


class ActionResult(BaseModel):
    id: int
    status: str
    result: dict = {}


class UserResponse(BaseModel):
    username: str
    role: str


class HealthResponse(BaseModel):
    status: str


class SignupRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=32,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    )
    password: str = Field(min_length=12, max_length=128)


class DocumentResponse(ORMModel):
    id: int
    filename: str
    version: int
    status: str
    created_at: datetime