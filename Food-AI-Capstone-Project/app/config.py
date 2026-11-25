import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://food_app:change-me@127.0.0.1:3306/food_assistant?charset=utf8mb4",
    )
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
    gemini_embedding_model: str = os.getenv(
        "GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"
    )
    internal_api_base_url: str = os.getenv(
        "INTERNAL_API_BASE_URL", "http://127.0.0.1:8000"
    ).rstrip("/")
    chroma_path: Path = PROJECT_ROOT / os.getenv("CHROMA_PATH", "storage/chroma")
    document_path: Path = PROJECT_ROOT / os.getenv(
        "DOCUMENT_PATH", "storage/documents"
    )
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", "10485760"))
    demo_admin_username: str = os.getenv("DEMO_ADMIN_USERNAME", "admin")
    demo_admin_password: str = os.getenv(
        "DEMO_ADMIN_PASSWORD", "ChangeThisAdminPassword!"
    )
    demo_user_one_username: str = os.getenv("DEMO_USER_ONE_USERNAME", "maya")
    demo_user_one_password: str = os.getenv(
        "DEMO_USER_ONE_PASSWORD", "ChangeThisMayaPassword!"
    )
    demo_user_two_username: str = os.getenv("DEMO_USER_TWO_USERNAME", "arjun")
    demo_user_two_password: str = os.getenv(
        "DEMO_USER_TWO_PASSWORD", "ChangeThisArjunPassword!"
    )


settings = Settings()