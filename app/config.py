from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Firebase
    firebase_credentials_path: str
    firebase_web_api_key: str
    
    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # API
    api_title: str = "Edel-SocialApp API"
    api_version: str = "1.0.0"
    api_description: str = "API para red social anónima con moderación automática"
    
    class Config:
        env_file = ".env"

settings = Settings()