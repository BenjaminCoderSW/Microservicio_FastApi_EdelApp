from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

class CreatePostRequest(BaseModel):
    """Modelo para crear un nuevo post"""
    content: str = Field(..., min_length=1, max_length=500, description="Contenido del post (máximo 500 caracteres)")
    image_url: Optional[str] = Field(None, description="URL de imagen opcional")
    
    @validator('content')
    def validate_content(cls, v):
        if not v.strip():
            raise ValueError('El contenido no puede estar vacío')
        return v.strip()
    
    @validator('image_url')
    def validate_image_url(cls, v):
        if v is not None and v != "":
            if not v.startswith(('http://', 'https://')):
                raise ValueError('La imagen debe ser una URL válida')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "Este es mi primer post en Edel-SocialApp!",
                "image_url": "https://storage.googleapis.com/bucket/image.jpg"
            }
        }

class PostResponse(BaseModel):
    """Modelo para respuesta de un post"""
    post_id: str
    user_id: str
    alias: str
    content: str
    image_url: Optional[str] = None
    created_at: datetime
    likes_count: int = 0
    comments_count: int = 0
    is_deleted: bool = False
    user_liked: Optional[bool] = None  # NUEVO: indica si el usuario actual dio like
    
    class Config:
        json_schema_extra = {
            "example": {
                "post_id": "post123abc",
                "user_id": "user456xyz",
                "alias": "UsuarioAnonimo",
                "content": "Este es mi primer post!",
                "image_url": "https://storage.googleapis.com/bucket/image.jpg",
                "created_at": "2024-10-21T10:30:00",
                "likes_count": 5,
                "comments_count": 2,
                "is_deleted": False,
                "user_liked": True  # NUEVO
            }
        }

class PostListResponse(BaseModel):
    """Modelo para lista paginada de posts"""
    posts: List[PostResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "posts": [],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "has_more": True
            }
        }

class CreatePostResponse(BaseModel):
    """Modelo para respuesta de creación de post"""
    message: str
    post_id: str
    moderation_status: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Post creado exitosamente",
                "post_id": "post123abc",
                "moderation_status": "approved"
            }
        }

class ModerationResult(BaseModel):
    """Modelo para resultado de moderación"""
    is_safe: bool
    reason: Optional[str] = None
    flagged_by: List[str] = []
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_safe": True,
                "reason": None,
                "flagged_by": []
            }
        }