from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime

class ProfileResponse(BaseModel):
    """Modelo para respuesta de perfil"""
    user_id: str
    email: str
    alias: str
    created_at: datetime
    is_admin: bool = False
    profile_image: Optional[str] = None
    posts_count: int = 0
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "abc123xyz",
                "email": "usuario@ejemplo.com",
                "alias": "UsuarioAnonimo",
                "created_at": "2024-10-13T10:30:00",
                "is_admin": False,
                "profile_image": "https://storage.googleapis.com/...",
                "posts_count": 5
            }
        }

class UpdateProfileRequest(BaseModel):
    """Modelo para actualizar perfil"""
    alias: Optional[str] = Field(None, min_length=3, max_length=20, description="Nuevo alias (opcional)")
    profile_image: Optional[str] = Field(None, description="URL de imagen de perfil (opcional)")
    
    @validator('alias')
    def validate_alias(cls, v):
        if v is not None:
            if not v.replace('_', '').replace('-', '').isalnum():
                raise ValueError('El alias solo puede contener letras, números, guiones y guiones bajos')
        return v
    
    @validator('profile_image')
    def validate_profile_image(cls, v):
        if v is not None and v != "":
            # Validar que sea una URL válida (básico)
            if not v.startswith(('http://', 'https://')):
                raise ValueError('La imagen de perfil debe ser una URL válida')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "alias": "NuevoAlias",
                "profile_image": "https://storage.googleapis.com/bucket/image.jpg"
            }
        }

class UpdateProfileResponse(BaseModel):
    """Modelo para respuesta de actualización de perfil"""
    message: str
    user_id: str
    updated_fields: list[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Perfil actualizado exitosamente",
                "user_id": "abc123xyz",
                "updated_fields": ["alias", "profile_image"]
            }
        }