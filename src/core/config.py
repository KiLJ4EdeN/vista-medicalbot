from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
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
    database_url: str = ""

    minio_host: str = "localhost"
    minio_port: int = 9000
    minio_endpoint: str = ""
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

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_url: str = ""
    qdrant_collection: str = "medical_knowledge"
    knowledge_chunk_size: int = Field(default=1200, gt=100)
    knowledge_chunk_overlap: int = Field(default=200, ge=0)
    embedding_batch_size: int = Field(default=32, gt=0, le=100)
    rag_result_limit: int = Field(default=6, gt=0, le=50)
    qdrant_bm25_model: str = "Qdrant/bm25"
    agent_recursion_limit: int = Field(default=12, ge=2, le=50)
    chat_history_limit: int = Field(default=50, gt=0, le=500)
    online_window_minutes: int = Field(default=15, gt=0, le=1440)

    jwt_secret: SecretStr = SecretStr("change-me")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    admin_api_key: SecretStr = SecretStr("")

    llm_api_url: str = "https://dr7.ai/api/v1/medical/chat/completions"
    llm_model: str = "baichuan-m3"
    llm_provider_type: str = "openai"
    llm_api_key: SecretStr = SecretStr("")

    multimodal_api_url: str = "https://openrouter.ai/api/v1/chat/completions"
    multimodal_model: str = "google/gemini-3.5-flash"
    multimodal_provider_type: str = "openai"
    multimodal_api_key: SecretStr = SecretStr("")

    embedding_api_url: str = "https://openrouter.ai/api/v1/embeddings"
    embedding_model: str = "baai/bge-m3"
    embedding_api_key: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def assemble_urls(self) -> "Settings":
        if not self.database_url:
            pw = self.postgres_password.get_secret_value()
            self.database_url = (
                f"postgresql+asyncpg://{self.postgres_user}:{pw}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        if not self.minio_endpoint:
            self.minio_endpoint = f"{self.minio_host}:{self.minio_port}"
        if not self.qdrant_url:
            self.qdrant_url = f"http://{self.qdrant_host}:{self.qdrant_port}"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_runtime_settings() -> None:
    settings = get_settings()
    if len(settings.jwt_secret.get_secret_value()) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 characters")
    if len(settings.admin_api_key.get_secret_value()) < 16:
        raise RuntimeError("ADMIN_API_KEY must contain at least 16 characters")
