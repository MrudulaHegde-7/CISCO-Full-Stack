from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    department: str = Field(min_length=2, max_length=100)
    salary: float = Field(ge=0)


class EmployeeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    department: str | None = Field(default=None, min_length=2, max_length=100)
    salary: float | None = Field(default=None, ge=0)


class EmployeeResponse(BaseModel):
    id: int
    name: str
    email: str
    department: str
    salary: float
