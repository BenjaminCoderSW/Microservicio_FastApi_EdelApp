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
    fcm_token: Optional[str] = None
    posts_count: int = 0
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "abc123xyz",
                "email": "usuario@ejemplo.com",
                "alias": "Alberto Francisco Torres",
                "created_at": "2024-10-13T10:30:00",
                "is_admin": False,
                "profile_image": "https://storage.googleapis.com/...",
                "fcm_token": "dXpZL3J2k4z...",
                "posts_count": 5
            }
        }

class UpdateProfileRequest(BaseModel):
    """Modelo para actualizar perfil"""
    alias: Optional[str] = Field(None, min_length=3, max_length=50, description="Nuevo alias (opcional)")
    profile_image: Optional[str] = Field(None, description="URL de imagen de perfil (opcional)")
    fcm_token: Optional[str] = Field(None, description="Token FCM del dispositivo para notificaciones push (opcional)")
    
    @validator('alias')
    def validate_alias(cls, v):
        if v is not None:
            # Eliminar espacios al inicio y final
            v = v.strip()
            
            # Validar longitud después de eliminar espacios
            if len(v) < 3:
                raise ValueError('El alias debe tener al menos 3 caracteres')
            if len(v) > 50:
                raise ValueError('El alias no puede tener más de 50 caracteres')
            
            # Permitir letras, números, espacios, guiones y guiones bajos
            # Remover espacios temporalmente para validar caracteres
            alias_sin_espacios = v.replace(' ', '').replace('_', '').replace('-', '')
            
            if not alias_sin_espacios.isalnum():
                raise ValueError('El alias solo puede contener letras, números, espacios, guiones y guiones bajos')
            
            # No permitir espacios múltiples consecutivos
            if '  ' in v:
                raise ValueError('El alias no puede tener espacios múltiples consecutivos')
        
        return v
    
    @validator('profile_image')
    def validate_profile_image(cls, v):
        if v is not None and v != "":
            # Validar que sea una URL válida (básico)
            if not v.startswith(('http://', 'https://')):
                raise ValueError('La imagen de perfil debe ser una URL válida')
        return v
    
    @validator('fcm_token')
    def validate_fcm_token(cls, v):
        if v is not None and v != "":
            # Validar que no esté vacío y tenga longitud razonable
            if len(v) < 50:
                raise ValueError('Token FCM inválido (demasiado corto)')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "alias": "Alberto Francisco Torres Perez",
                "profile_image": "https://storage.googleapis.com/bucket/image.jpg",
                "fcm_token": "dXpZL3J2k4zNhMw1hGkhYb4lrZRki1FuCbNLGAvSh8dXpZL3..."
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
                "updated_fields": ["alias", "profile_image", "fcm_token"]
            }
        }