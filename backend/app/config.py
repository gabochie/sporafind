from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""
    companies_house_api_key: str = ""
    auth_secret: str = ""
    admin_key: str = ""
    public_api_key: str = ""
    redis_url: str = "redis://localhost:6379"
    cors_origins: str = "http://localhost:8000,http://localhost:3000,https://www.sporafind.com"
    environment: str = "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
