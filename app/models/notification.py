from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class SendNotificationRequest(BaseModel):
    """Solicitud para enviar notificación push"""
    user_id: str = Field(..., description="ID del usuario que recibirá la notificación")
    title: str = Field(..., max_length=100, description="Título de la notificación")
    body: str = Field(..., max_length=500, description="Cuerpo de la notificación")
    data: Optional[dict] = Field(None, description="Datos adicionales opcionales")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "abc123xyz",
                "title": "Nuevo like en tu post",
                "body": "A UsuarioAnonimo le gustó tu post",
                "data": {
                    "post_id": "post123",
                    "type": "like"
                }
            }
        }

class NotificationResponse(BaseModel):
    """Respuesta al enviar notificación"""
    success: bool
    message: str
    notification_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Notificación enviada exitosamente",
                "notification_id": "notif123"
            }
        }

class NotificationInDB(BaseModel):
    """Modelo de notificación en Firestore"""
    notification_id: str
    user_id: str
    title: str
    body: str
    data: Optional[dict] = None
    created_at: datetime
    is_read: bool = False
    type: str  # like, comment, follow, admin, etc.
    
    class Config:
        json_schema_extra = {
            "example": {
                "notification_id": "notif123",
                "user_id": "user456",
                "title": "Nuevo comentario",
                "body": "UsuarioAnonimo comentó en tu post",
                "data": {"post_id": "post123", "comment_id": "comment456"},
                "created_at": "2025-10-28T10:30:00Z",
                "is_read": False,
                "type": "comment"
            }
        }

class GetNotificationsResponse(BaseModel):
    """Lista de notificaciones del usuario"""
    notifications: List[NotificationInDB]
    total: int
    unread_count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "notifications": [],
                "total": 15,
                "unread_count": 3
            }
        }

class MarkAsReadRequest(BaseModel):
    """Marcar notificaciones como leídas"""
    notification_ids: List[str] = Field(..., description="IDs de notificaciones a marcar como leídas")
    
    class Config:
        json_schema_extra = {
            "example": {
                "notification_ids": ["notif123", "notif456"]
            }
        }