from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Firebase
    firebase_credentials_path: str
    firebase_web_api_key: str
    firebase_storage_bucket: Optional[str] = None
    
    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Moderation APIs
    moderatecontent_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    sightengine_api_user: Optional[str] = None
    sightengine_api_secret: Optional[str] = None
    # PurgoMalum no requiere API key (es gratuito)
    
    # API
    api_title: str = "Edel-SocialApp API"
    api_version: str = "1.0.0"
    api_description: str = "API para red social anónima con moderación automática"
    
    class Config:
        env_file = ".env"

settings = Settings()