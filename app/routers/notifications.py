from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.notification import (
    SendNotificationRequest,
    NotificationResponse,
    NotificationInDB,
    GetNotificationsResponse,
    MarkAsReadRequest
)
from app.services.firebase_service import firebase_service
from app.services.fcm_service import fcm_service
from app.utils.auth_utils import verify_token
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/notifications", tags=["Notifications"])
security = HTTPBearer()

@router.post("/send", response_model=NotificationResponse, status_code=status.HTTP_200_OK)
async def send_notification(
    request: SendNotificationRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Enviar notificación push a un usuario específico
    
    - Busca el FCM token del usuario en Firestore
    - Envía la notificación usando Firebase Admin SDK (HTTP v1)
    - Guarda la notificación en Firestore para historial
    
    **Header requerido:**
    - Authorization: Bearer {token}
    
    **Body:**
    - user_id: ID del usuario destinatario
    - title: Título de la notificación
    - body: Cuerpo de la notificación
    - data: Datos adicionales opcionales
    
    **Respuesta:**
    - success: Si se envió correctamente
    - message: Mensaje descriptivo
    - notification_id: ID de la notificación guardada
    """
    try:
        # Verificar token
        token = credentials.credentials
        current_user = verify_token(token)
        
        print(f"📤 Enviando notificación a usuario: {request.user_id}")
        
        # Enviar notificación
        result = fcm_service.send_notification_to_user(
            user_id=request.user_id,
            title=request.title,
            body=request.body,
            data=request.data if request.data else {},
            notification_type=request.data.get('type', 'general') if request.data else 'general'
        )
        
        return NotificationResponse(
            success=result["success"],
            message=result["message"],
            notification_id=result.get("notification_id")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al enviar notificación: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al enviar notificación: {str(e)}"
        )

@router.get("/", response_model=GetNotificationsResponse)
async def get_notifications(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    limit: int = Query(20, ge=1, le=100, description="Número máximo de notificaciones"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    unread_only: bool = Query(False, description="Solo notificaciones no leídas")
):
    """
    Obtener notificaciones del usuario autenticado
    
    - Retorna notificaciones ordenadas por fecha (más recientes primero)
    - Incluye contador de no leídas
    - Soporta paginación
    
    **Header requerido:**
    - Authorization: Bearer {token}
    
    **Query params:**
    - limit: Número máximo de notificaciones (default: 20, max: 100)
    - offset: Offset para paginación (default: 0)
    - unread_only: Solo notificaciones no leídas (default: false)
    
    **Respuesta:**
    - notifications: Lista de notificaciones
    - total: Total de notificaciones
    - unread_count: Contador de no leídas
    """
    try:
        # Verificar token
        token = credentials.credentials
        current_user = verify_token(token)
        user_id = current_user['uid']
        
        db = firebase_service.get_db()
        
        # Query base
        query = db.collection('notifications').where('user_id', '==', user_id)
        
        # Filtrar solo no leídas si se solicita
        if unread_only:
            query = query.where('is_read', '==', False)
        
        # Ordenar por fecha descendente
        query = query.order_by('created_at', direction='DESCENDING')
        
        # Obtener todas las notificaciones (para contar)
        all_notifications = list(query.stream())
        total = len(all_notifications)
        
        # Aplicar paginación
        notifications_page = all_notifications[offset:offset + limit]
        
        # Convertir a NotificationInDB
        notifications_list = []
        for notif_doc in notifications_page:
            notif_data = notif_doc.to_dict()
            notifications_list.append(NotificationInDB(
                notification_id=notif_data['notification_id'],
                user_id=notif_data['user_id'],
                title=notif_data['title'],
                body=notif_data['body'],
                data=notif_data.get('data'),
                created_at=notif_data['created_at'],
                is_read=notif_data.get('is_read', False),
                type=notif_data.get('type', 'general')
            ))
        
        # Contar no leídas
        unread_query = db.collection('notifications')\
            .where('user_id', '==', user_id)\
            .where('is_read', '==', False)\
            .stream()
        unread_count = len(list(unread_query))
        
        print(f"✅ Notificaciones obtenidas: usuario={user_id}, total={total}, no_leídas={unread_count}")
        
        return GetNotificationsResponse(
            notifications=notifications_list,
            total=total,
            unread_count=unread_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al obtener notificaciones: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener notificaciones: {str(e)}"
        )

@router.put("/mark-as-read", status_code=status.HTTP_200_OK)
async def mark_notifications_as_read(
    request: MarkAsReadRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Marcar notificaciones como leídas
    
    - Actualiza el campo is_read a true
    - Solo el propietario puede marcar sus notificaciones
    
    **Header requerido:**
    - Authorization: Bearer {token}
    
    **Body:**
    - notification_ids: Lista de IDs de notificaciones
    
    **Respuesta:**
    - Mensaje de éxito
    - Contador de notificaciones actualizadas
    """
    try:
        # Verificar token
        token = credentials.credentials
        current_user = verify_token(token)
        user_id = current_user['uid']
        
        db = firebase_service.get_db()
        
        # Actualizar cada notificación
        updated_count = 0
        for notification_id in request.notification_ids:
            notif_doc = db.collection('notifications').document(notification_id).get()
            
            if notif_doc.exists:
                notif_data = notif_doc.to_dict()
                
                # Verificar que pertenece al usuario
                if notif_data['user_id'] == user_id:
                    db.collection('notifications').document(notification_id).update({
                        'is_read': True,
                        'read_at': datetime.utcnow()
                    })
                    updated_count += 1
        
        print(f"✅ Notificaciones marcadas como leídas: {updated_count}/{len(request.notification_ids)}")
        
        return {
            "message": f"{updated_count} notificaciones marcadas como leídas",
            "updated_count": updated_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al marcar notificaciones: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al marcar notificaciones: {str(e)}"
        )

@router.delete("/{notification_id}", status_code=status.HTTP_200_OK)
async def delete_notification(
    notification_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Eliminar notificación del historial
    
    - Solo el propietario puede eliminar sus notificaciones
    - Eliminación permanente de Firestore
    
    **Header requerido:**
    - Authorization: Bearer {token}
    
    **Respuesta:**
    - Mensaje de confirmación
    """
    try:
        # Verificar token
        token = credentials.credentials
        current_user = verify_token(token)
        user_id = current_user['uid']
        
        db = firebase_service.get_db()
        
        # Obtener notificación
        notif_doc = db.collection('notifications').document(notification_id).get()
        
        if not notif_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notificación no encontrada"
            )
        
        notif_data = notif_doc.to_dict()
        
        # Verificar que pertenece al usuario
        if notif_data['user_id'] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para eliminar esta notificación"
            )
        
        # Eliminar
        db.collection('notifications').document(notification_id).delete()
        
        print(f"✅ Notificación eliminada: {notification_id}")
        
        return {
            "message": "Notificación eliminada exitosamente",
            "notification_id": notification_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al eliminar notificación: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar notificación: {str(e)}"
        )