from pydantic import PostgresDsn, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER = "changethis"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "InfraScope"
    ENVIRONMENT: str = "development"

    SECRET_KEY: str = _PLACEHOLDER

    @model_validator(mode="after")
    def validate_secret_key(self) -> Settings:
        if self.ENVIRONMENT == "production" and self.SECRET_KEY == _PLACEHOLDER:
            raise ValueError(
                "SECRET_KEY must be set to a secure value in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return self
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    FIRST_SUPERUSER_EMAIL: str = "admin@infrascope.dev"
    FIRST_SUPERUSER_PASSWORD: str = "changethis"

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "infrascope"

    REDIS_URL: str = "redis://localhost:6379/0"

    SCAN_SUBNET: str = ""
    SCAN_PORTS: str = "9100,631,80,443"
    SCAN_MAX_HOSTS: int = 4096
    SCAN_TCP_TIMEOUT: float = 1.0
    SCAN_TCP_RETRIES: int = 1
    SCAN_TCP_CONCURRENCY: int = 256

    DOMAIN: str = "infrascope.local"

    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_SERVER,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    @computed_field
    @property
    def ASYNC_DATABASE_URI(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_SERVER,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )


settings = Settings()
