from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# ==================== LIKES ====================

class LikeResponse(BaseModel):
    """Respuesta al dar/quitar like"""
    message: str
    post_id: str
    likes_count: int
    user_liked: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Like agregado exitosamente",
                "post_id": "abc123xyz",
                "likes_count": 42,
                "user_liked": True
            }
        }

class LikeStatus(BaseModel):
    """Estado de like de un usuario en un post"""
    post_id: str
    user_liked: bool
    likes_count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "post_id": "abc123xyz",
                "user_liked": True,
                "likes_count": 42
            }
        }

# ==================== COMENTARIOS ====================

class CreateCommentRequest(BaseModel):
    """Solicitud para crear comentario"""
    content: str = Field(
        ..., 
        min_length=1, 
        max_length=500, 
        description="Contenido del comentario (1-500 caracteres)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "¡Excelente post! Me encanta este contenido."
            }
        }

class CommentResponse(BaseModel):
    """Respuesta de un comentario individual"""
    comment_id: str
    post_id: str
    user_id: str
    alias: str
    content: str
    created_at: datetime
    is_deleted: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "comment_id": "comment123",
                "post_id": "post456",
                "user_id": "user789",
                "alias": "UsuarioAnonimo",
                "content": "¡Excelente post! Muy interesante.",
                "created_at": "2025-10-26T10:30:00Z",
                "is_deleted": False
            }
        }

class CommentListResponse(BaseModel):
    """Lista de comentarios con paginación"""
    comments: List[CommentResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "comments": [
                    {
                        "comment_id": "comment123",
                        "post_id": "post456",
                        "user_id": "user789",
                        "alias": "UsuarioAnonimo",
                        "content": "¡Excelente post!",
                        "created_at": "2025-10-26T10:30:00Z",
                        "is_deleted": False
                    }
                ],
                "total": 15,
                "page": 1,
                "page_size": 20,
                "has_more": False
            }
        }

# ==================== REPORTES ====================

class CreateReportRequest(BaseModel):
    """Solicitud para reportar contenido"""
    reason: str = Field(
        ..., 
        description="Razón del reporte (spam, harassment, violence, hate_speech, misinformation, other)"
    )
    description: Optional[str] = Field(
        None, 
        max_length=500, 
        description="Descripción adicional del problema"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "reason": "spam",
                "description": "Este post es publicidad no deseada de productos"
            }
        }

class ReportResponse(BaseModel):
    """Respuesta de un reporte"""
    report_id: str
    post_id: str
    reported_by: str
    reason: str
    description: Optional[str]
    status: str  # pending, reviewed, resolved
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "report_id": "report123",
                "post_id": "post456",
                "reported_by": "user789",
                "reason": "spam",
                "description": "Publicidad no deseada",
                "status": "pending",
                "created_at": "2025-10-26T10:30:00Z",
                "reviewed_at": None,
                "reviewed_by": None
            }
        }

class ReportListResponse(BaseModel):
    """Lista de reportes (solo admin)"""
    reports: List[ReportResponse]
    total: int
    pending_count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "reports": [
                    {
                        "report_id": "report123",
                        "post_id": "post456",
                        "reported_by": "user789",
                        "reason": "spam",
                        "description": "Publicidad no deseada",
                        "status": "pending",
                        "created_at": "2025-10-26T10:30:00Z",
                        "reviewed_at": None,
                        "reviewed_by": None
                    }
                ],
                "total": 5,
                "pending_count": 3
            }
        }

class UpdateReportStatusRequest(BaseModel):
    """Solicitud para actualizar estado de reporte"""
    status: str = Field(
        ..., 
        description="Nuevo estado (reviewed, resolved)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "reviewed"
            }
        }