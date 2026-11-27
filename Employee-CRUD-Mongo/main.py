import os

from bson import ObjectId
from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError


app = FastAPI(title="Employee CRUD")
client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
employees = client[os.getenv("MONGO_DB", "employee_db")]["employees"]


class Employee(BaseModel):
	name: str = Field(min_length=1)
	email: str = Field(min_length=1)
	department: str = Field(min_length=1)
	salary: float = Field(ge=0)


class EmployeeResponse(Employee):
	id: int | str


class EmployeeCreate(Employee):
	id: int = Field(strict=True, ge=1, le=9223372036854775807)


def employee_id(value: str) -> int | str | ObjectId:
	if value.isascii() and value.isdecimal() and int(value) <= 9223372036854775807:
		if employees.find_one({"_id": value}) is not None:
			return value
		return int(value)
	if ObjectId.is_valid(value) and employees.find_one({"_id": ObjectId(value)}) is not None:
		return ObjectId(value)
	return value


def employee_response(document: dict) -> dict:
	identifier = document["_id"]
	return {**document, "id": str(identifier) if isinstance(identifier, ObjectId) else identifier}


@app.post("/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(employee: EmployeeCreate):
	document = employee.model_dump(exclude={"id"})
	document["_id"] = employee.id
	if employees.find_one({"_id": str(employee.id)}) is not None:
		raise HTTPException(status_code=409, detail="Employee ID already exists")
	try:
		employees.insert_one(document)
	except DuplicateKeyError:
		raise HTTPException(status_code=409, detail="Employee ID already exists")
	return employee_response(document)


@app.get("/employees", response_model=list[EmployeeResponse])
def list_employees():
	return [employee_response(document) for document in employees.find()]


@app.get("/employees/{id}", response_model=EmployeeResponse)
def get_employee(id: str):
	document = employees.find_one({"_id": employee_id(id)})
	if document is None:
		raise HTTPException(status_code=404, detail="Employee not found")
	return employee_response(document)


@app.put("/employees/{id}", response_model=EmployeeResponse)
def update_employee(id: str, employee: Employee):
	document = employees.find_one_and_update(
		{"_id": employee_id(id)},
		{"$set": employee.model_dump()},
		return_document=ReturnDocument.AFTER,
	)
	if document is None:
		raise HTTPException(status_code=404, detail="Employee not found")
	return employee_response(document)


@app.delete("/employees/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(id: str):
	result = employees.delete_one({"_id": employee_id(id)})
	if result.deleted_count == 0:
		raise HTTPException(status_code=404, detail="Employee not found")
	return Response(status_code=status.HTTP_204_NO_CONTENT)
