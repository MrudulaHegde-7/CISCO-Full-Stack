from unittest.mock import MagicMock

from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

import main


client = TestClient(main.app)
employee = {"name": "Alex", "email": "alex@example.com", "department": "IT", "salary": 50000}


def test_employee_crud(monkeypatch):
    collection = MagicMock()
    monkeypatch.setattr(main, "employees", collection)
    employee_id = 101
    document = {"_id": employee_id, **employee}
    collection.find.return_value = [document]
    collection.find_one.side_effect = [None, None, document, None, None]
    collection.find_one_and_update.return_value = document
    collection.delete_one.return_value.deleted_count = 1

    response = client.post("/employees", json={"id": employee_id, **employee})
    assert response.status_code == 201
    assert response.json() == {"id": employee_id, **employee}
    assert client.get("/employees").json() == [response.json()]
    assert client.get(f"/employees/{employee_id}").json() == response.json()
    assert client.put(f"/employees/{employee_id}", json=employee).json() == response.json()
    assert client.delete(f"/employees/{employee_id}").status_code == 204
    collection.insert_one.assert_called_once_with(document)
    collection.find_one_and_update.assert_called_once()
    collection.delete_one.assert_called_once_with({"_id": employee_id})


def test_missing_and_duplicate_employee(monkeypatch):
    collection = MagicMock()
    monkeypatch.setattr(main, "employees", collection)
    collection.find_one.return_value = None
    collection.find_one_and_update.return_value = None
    collection.delete_one.return_value.deleted_count = 0
    missing_id = 404

    assert client.get(f"/employees/{missing_id}").status_code == 404
    assert client.put(f"/employees/{missing_id}", json=employee).status_code == 404
    assert client.delete(f"/employees/{missing_id}").status_code == 404
    assert client.post("/employees", json=employee).status_code == 422
    assert client.post("/employees", json={"id": "1", **employee}).status_code == 422
    assert client.post("/employees", json={"id": 0, **employee}).status_code == 422
    assert client.post("/employees", json={"id": 1, **employee, "salary": -1}).status_code == 422
    collection.insert_one.side_effect = DuplicateKeyError("duplicate")
    assert client.post("/employees", json={"id": 1, **employee}).status_code == 409


def test_existing_mongodb_id(monkeypatch):
    collection = MagicMock()
    monkeypatch.setattr(main, "employees", collection)
    object_id = ObjectId()
    document = {"_id": object_id, **employee}
    collection.find_one.return_value = document

    assert client.get(f"/employees/{object_id}").json() == {"id": str(object_id), **employee}


def test_existing_string_ids(monkeypatch):
    collection = MagicMock()
    monkeypatch.setattr(main, "employees", collection)
    document = {"_id": "101", **employee}
    collection.find_one.return_value = document

    assert client.get("/employees/101").json() == {"id": "101", **employee}
    assert client.post("/employees", json={"id": 101, **employee}).status_code == 409

    document["_id"] = "EMP-101"
    assert client.get("/employees/EMP-101").json() == {"id": "EMP-101", **employee}