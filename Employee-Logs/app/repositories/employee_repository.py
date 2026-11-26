from app.models import EmployeeAlreadyExistsError, EmployeeNotFoundError


class EmployeeRepository:
    def __init__(self) -> None:
        self._employees: dict[int, dict] = {}
        self._emails: set[str] = set()
        self._next_id = 1

    def list_all(self) -> list[dict]:
        return [employee.copy() for employee in self._employees.values()]

    def get(self, employee_id: int) -> dict:
        employee = self._employees.get(employee_id)
        if employee is None:
            raise EmployeeNotFoundError(f"Employee {employee_id} not found")
        return employee.copy()

    def create(self, data: dict) -> dict:
        email = data["email"].lower()
        if email in self._emails:
            raise EmployeeAlreadyExistsError(f"Email {email} already exists")

        employee = {"id": self._next_id, **data, "email": email}
        self._employees[self._next_id] = employee
        self._emails.add(email)
        self._next_id += 1
        return employee.copy()

    def update(self, employee_id: int, data: dict) -> dict:
        employee = self._employees.get(employee_id)
        if employee is None:
            raise EmployeeNotFoundError(f"Employee {employee_id} not found")

        new_email = data.get("email")
        if new_email is not None:
            new_email = new_email.lower()
            if new_email != employee["email"] and new_email in self._emails:
                raise EmployeeAlreadyExistsError(f"Email {new_email} already exists")

        if new_email is not None:
            self._emails.discard(employee["email"])
            self._emails.add(new_email)

        employee.update(data)
        if new_email is not None:
            employee["email"] = new_email
        return employee.copy()

    def delete(self, employee_id: int) -> None:
        employee = self._employees.get(employee_id)
        if employee is None:
            raise EmployeeNotFoundError(f"Employee {employee_id} not found")
        self._emails.discard(employee["email"])
        del self._employees[employee_id]
