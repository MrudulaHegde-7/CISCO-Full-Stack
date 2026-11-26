from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.orm import Session

from app.db.database import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)
from app.db.models import DeviceRow
from app.models import DeviceCreate
from app.repositories.sqlalchemy_device_repository import SQLAlchemyDeviceRepository


def main() -> None:
    with TemporaryDirectory() as temporary_directory:
        database_path = Path(temporary_directory) / "crud-demo.db"
        engine = create_database_engine(f"sqlite:///{database_path}")
        initialize_database(engine)
        session_factory = create_session_factory(engine)

        with Session(engine) as session:
            repository = SQLAlchemyDeviceRepository(session)
            device = DeviceCreate(
                device_id="DEMO-CRUD",
                name="Temporary Demo Router",
                device_type="router",
                ip_address="192.168.10.99",
                status="online",
            )

            created = repository.add_device(device)
            session.commit()
            print(f"Create: {created.device_id} saved in temporary SQLite")

            found = repository.get_device(created.device_id)
            print(f"Read: {found.device_id} ({found.status})")

            updated = repository.update_status(created.device_id, "offline")
            session.commit()
            print(f"Update: {updated.device_id} is now {updated.status}")

            row = session.get(DeviceRow, created.device_id)
            session.delete(row)
            session.commit()
            print(f"Delete: {created.device_id} removed from temporary SQLite")

        engine.dispose()


if __name__ == "__main__":
    main()