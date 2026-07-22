from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: SecretStr = SecretStr("postgres")
    postgres_db: str = "postgres"

    minio_endpoint: str = "localhost:9000"
    minio_public_endpoint: str | None = None
    minio_public_secure: bool | None = None
    minio_access_key: str = "minioadmin"
    minio_secret_key: SecretStr = SecretStr("minioadmin")
    minio_bucket: str = "files"
    minio_secure: bool = False
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, gt=0)
    max_audio_bytes: int = Field(default=25 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=100, gt=0)
    download_url_expire_minutes: int = Field(default=15, gt=0, le=1440)

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "medical_knowledge"
    knowledge_chunk_size: int = Field(default=1200, gt=100)
    knowledge_chunk_overlap: int = Field(default=200, ge=0)
    embedding_batch_size: int = Field(default=32, gt=0, le=100)
    rag_result_limit: int = Field(default=6, gt=0, le=50)
    qdrant_bm25_model: str = "Qdrant/bm25"
    agent_recursion_limit: int = Field(default=12, ge=2, le=50)
    chat_history_limit: int = Field(default=50, gt=0, le=500)
    online_window_minutes: int = Field(default=15, gt=0, le=1440)

    admin_api_key: SecretStr = SecretStr("")

    llm_api_url: str = "https://dr7.ai/api/v1/medical/chat/completions"
    llm_model: str = "baichuan-m3"
    llm_api_key: SecretStr = SecretStr("")

    multimodal_api_url: str = "https://openrouter.ai/api/v1/chat/completions"
    multimodal_model: str = "google/gemini-3.5-flash"
    multimodal_api_key: SecretStr = SecretStr("")

    embedding_api_url: str = "https://openrouter.ai/api/v1/embeddings"
    embedding_model: str = "baai/bge-m3"
    embedding_api_key: SecretStr = SecretStr("")

    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password.get_secret_value())
        database = quote_plus(self.postgres_db)
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{database}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_runtime_settings() -> None:
    settings = get_settings()
    if len(settings.admin_api_key.get_secret_value()) < 16:
        raise RuntimeError("ADMIN_API_KEY must contain at least 16 characters")
