from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    INSTAGRAM_ACCESS_TOKEN: str
    INSTAGRAM_VERIFY_TOKEN: str
    INSTAGRAM_APP_SECRET: str
    INSTAGRAM_PAGE_ID: str = ""
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    MONGODB_URI: str
    MONGODB_DB_NAME: str = "instagram_bot"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    BOOKING_LINK: str = "https://propest.ai/adviesgesprek"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
