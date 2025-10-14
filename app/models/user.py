from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime

class RegisterRequest(BaseModel):
    """Modelo para solicitud de registro"""
    email: EmailStr
    password: str = Field(..., min_length=6, description="Contraseña mínimo 6 caracteres")
    alias: str = Field(..., min_length=3, max_length=20, description="Nombre de usuario (alias)")
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('La contraseña debe tener al menos 6 caracteres')
        return v
    
    @validator('alias')
    def validate_alias(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('El alias solo puede contener letras, números, guiones y guiones bajos')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "usuario@ejemplo.com",
                "password": "Password123!",
                "alias": "UsuarioAnonimo"
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
                "alias": "UsuarioAnonimo",
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
                "alias": "UsuarioAnonimo",
                "created_at": "2024-10-13T10:30:00",
                "is_admin": False,
                "profile_image": None
            }
        }