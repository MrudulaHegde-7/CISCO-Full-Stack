from app.logger import get_logger
from app.repositories.employee_repository import EmployeeRepository


logger = get_logger()


class EmployeeService:
    def __init__(self, repository: EmployeeRepository) -> None:
        self.repository = repository

    def list_employees(self) -> list[dict]:
        employees = self.repository.list_all()
        logger.info("Listed %d employees", len(employees))
        return employees

    def get_employee(self, employee_id: int) -> dict:
        employee = self.repository.get(employee_id)
        logger.info("Fetched employee id=%d", employee_id)
        return employee

    def create_employee(self, data: dict) -> dict:
        employee = self.repository.create(data)
        logger.info("Created employee id=%d email=%s", employee["id"], employee["email"])
        return employee

    def update_employee(self, employee_id: int, data: dict) -> dict:
        employee = self.repository.update(employee_id, data)
        logger.info("Updated employee id=%d", employee_id)
        return employee

    def delete_employee(self, employee_id: int) -> None:
        self.repository.delete(employee_id)
        logger.info("Deleted employee id=%d", employee_id)
