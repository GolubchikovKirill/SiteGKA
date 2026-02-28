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
    ML_ENABLED: bool = True
    ML_SERVICE_URL: str = "http://ml-service:8010"
    POLLING_SERVICE_ENABLED: bool = False
    POLLING_SERVICE_URL: str = "http://polling-service:8011"
    DISCOVERY_SERVICE_ENABLED: bool = False
    DISCOVERY_SERVICE_URL: str = "http://discovery-service:8012"
    NETWORK_CONTROL_SERVICE_ENABLED: bool = False
    NETWORK_CONTROL_SERVICE_URL: str = "http://network-control-service:8013"
    INTERNAL_SERVICE_TOKEN: str = ""
    KAFKA_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_EVENT_TOPIC: str = "infrascope.events"
    ML_MIN_TRAIN_ROWS: int = 50
    ML_RETRAIN_HOUR_UTC: int = 2
    ML_SCORE_INTERVAL_MINUTES: int = 30

    SCAN_SUBNET: str = ""
    SCAN_PORTS: str = "9100,631,80,443"
    SCAN_MAX_HOSTS: int = 4096
    SCAN_TCP_TIMEOUT: float = 1.0
    SCAN_TCP_RETRIES: int = 1
    SCAN_TCP_CONCURRENCY: int = 256
    POLL_JITTER_MAX_MS: int = 150
    POLL_OFFLINE_CONFIRMATIONS: int = 2
    POLL_CIRCUIT_FAILURE_THRESHOLD: int = 4
    POLL_CIRCUIT_OPEN_SECONDS: int = 45
    POLL_RESILIENCE_STATE_TTL_SECONDS: int = 7200

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
