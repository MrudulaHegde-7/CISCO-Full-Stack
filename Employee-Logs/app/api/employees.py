from fastapi import APIRouter, HTTPException, status

from app.models import EmployeeAlreadyExistsError, EmployeeNotFoundError
from app.schemas import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.services.employee_service import EmployeeService


router = APIRouter(prefix="/employees", tags=["employees"])


def get_service() -> EmployeeService:
    from app.main import employee_service

    return employee_service


@router.get("", response_model=list[EmployeeResponse])
def list_employees() -> list[dict]:
    return get_service().list_employees()


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int) -> dict:
    try:
        return get_service().get_employee(employee_id)
    except EmployeeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(data: EmployeeCreate) -> dict:
    try:
        return get_service().create_employee(data.model_dump())
    except EmployeeAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: int, data: EmployeeUpdate) -> dict:
    try:
        updates = data.model_dump(exclude_unset=True)
        return get_service().update_employee(employee_id, updates)
    except EmployeeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EmployeeAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(employee_id: int) -> None:
    try:
        get_service().delete_employee(employee_id)
    except EmployeeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
