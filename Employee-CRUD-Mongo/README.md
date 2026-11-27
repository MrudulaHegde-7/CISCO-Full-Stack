# Employee CRUD with FastAPI and MongoDB

Start MongoDB, then from this folder install the dependencies in your virtual environment:

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://127.0.0.1:8000/docs to try the endpoints. The default MongoDB connection is `mongodb://localhost:27017`, using the `employee_db` database and `employees` collection. Set `MONGO_URI` or `MONGO_DB` to change those defaults.

Employee data example:

```json
{
  "id": 101,
  "name": "Alex",
  "email": "alex@example.com",
  "department": "IT",
  "salary": 50000
}
```

Use `POST /employees` to create, `GET /employees` to list, and `GET`, `PUT`, or `DELETE /employees/{id}` to read, replace, or delete an employee. Choose a unique positive whole number for the ID when creating an employee. `PUT` requires the other employee fields but does not change the ID. Existing string and MongoDB-generated IDs continue to work.

To run the tests, install `pytest` and `httpx`, then run `pytest test_main.py` from this folder.