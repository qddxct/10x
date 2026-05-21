from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    mysql_host: str = Field(default="localhost")
    mysql_port: int = Field(default=3306)
    mysql_user: str = Field(default="sporttery")
    mysql_password: str = Field(default="sporttery_pass")
    mysql_database: str = Field(default="sporttery_10x")

    jwt_secret: str = Field(default="dev-secret-change-me")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=43200)

    admin_default_phone: str = Field(default="13800000000")
    admin_default_name: str = Field(default="admin")
    admin_default_password: str = Field(default="Admin@1234")

    timezone: str = Field(default="Asia/Shanghai")
    log_level: str = Field(default="INFO")
    cors_origins: str = Field(default="http://localhost:3000")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
