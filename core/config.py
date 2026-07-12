from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AI SaaS Backend"
    app_version: str = "0.1.0"
    debug: bool = True

    db_host: str
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    
    otp_expire_minutes: int = 5
    otp_max_retries: int = 3
    refresh_token_expire_days: int = 7

    cors_origins: str = "http://localhost:3000"


    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


    class Config:
        env_file = ".env"


settings = Settings()