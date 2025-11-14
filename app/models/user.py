from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime

class RegisterRequest(BaseModel):
    """Modelo para solicitud de registro"""
    email: EmailStr
    password: str = Field(..., min_length=6, description="Contraseña mínimo 6 caracteres")
    alias: str = Field(..., min_length=3, max_length=50, description="Nombre de usuario (alias)")
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('La contraseña debe tener al menos 6 caracteres')
        return v
    
    @validator('alias')
    def validate_alias(cls, v):
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
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "usuario@ejemplo.com",
                "password": "Password123!",
                "alias": "Alberto Francisco Torres"
            }
        }

class LoginRequest(BaseModel):
    """Modelo para solicitud de login"""
    email: EmailStr
    password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "usuario@ejemplo.com",
                "password": "Password123!"
            }
        }

class LoginResponse(BaseModel):
    """Modelo para respuesta de login/registro"""
    token: str
    user_id: str
    alias: str
    email: str
    is_admin: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "user_id": "abc123xyz",
                "alias": "Alberto Francisco Torres",
                "email": "usuario@ejemplo.com",
                "is_admin": False
            }
        }

class UserInDB(BaseModel):
    """Modelo para usuario en Firestore"""
    uid: str
    email: str
    alias: str
    created_at: datetime
    is_admin: bool = False
    profile_image: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "uid": "abc123xyz",
                "email": "usuario@ejemplo.com",
                "alias": "Alberto Francisco Torres",
                "created_at": "2024-10-13T10:30:00",
                "is_admin": False,
                "profile_image": None
            }
        }