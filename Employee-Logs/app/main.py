from fastapi import FastAPI

from app.api.employees import router as employee_router
from app.logger import get_logger
from app.repositories.employee_repository import EmployeeRepository
from app.services.employee_service import EmployeeService


logger = get_logger()
employee_repository = EmployeeRepository()
employee_service = EmployeeService(employee_repository)

app = FastAPI(
    title="Employee Management API",
    version="1.0.0",
)
app.include_router(employee_router)


@app.on_event("startup")
def startup() -> None:
    logger.info("Employee Management API started")


@app.on_event("shutdown")
def shutdown() -> None:
    logger.info("Employee Management API stopped")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
