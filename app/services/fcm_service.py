from firebase_admin import messaging
from app.services.firebase_service import firebase_service
from typing import Optional, Dict
import uuid
from datetime import datetime

class FCMService:
    """Servicio para enviar notificaciones push usando Firebase Admin SDK (HTTP v1)"""
    
    def __init__(self):
        # Firebase Admin SDK ya está inicializado en firebase_service
        self.db = firebase_service.get_db()
    
    def send_notification(
        self,
        fcm_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        notification_type: str = "general"
    ) -> Dict:
        """
        Enviar notificación push a un dispositivo específico usando HTTP v1
        
        Args:
            fcm_token: Token FCM del dispositivo
            title: Título de la notificación
            body: Cuerpo de la notificación
            data: Datos adicionales (opcional)
            notification_type: Tipo de notificación (like, comment, etc.)
            
        Returns:
            Dict con resultado del envío
        """
        try:
            # IMPORTANTE: Asegurar que data tenga el tipo de notificación
            notification_data = data if data else {}
            notification_data['type'] = notification_type  # CRUCIAL para routing en frontend
            
            # Construir mensaje según FCM HTTP v1
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=notification_data,  # Los datos van aquí (NO en notification)
                token=fcm_token,
                android=messaging.AndroidConfig(
                    priority='high',
                    # REMOVIDO: click_action (Ali tiene razón, esto puede causar problemas)
                    notification=messaging.AndroidNotification(
                        sound='default',
                        # El channel_id ayuda a categorizar notificaciones
                        channel_id='edel_notifications'
                    )
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound='default',
                            badge=1,
                            # Para iOS, los datos deben estar aquí también
                            custom_data=notification_data
                        )
                    )
                )
            )
            
            # Enviar mensaje con Firebase Admin SDK (usa HTTP v1 automáticamente)
            response = messaging.send(message)
            
            print(f"✅ Notificación enviada exitosamente: {response}")
            
            return {
                "success": True,
                "message": "Notificación enviada exitosamente",
                "message_id": response
            }
            
        except messaging.UnregisteredError:
            print(f"⚠️ Token FCM no registrado o expirado")
            return {
                "success": False,
                "message": "Token FCM inválido o expirado",
                "error": "unregistered"
            }
        except messaging.SenderIdMismatchError:
            print(f"⚠️ Sender ID no coincide")
            return {
                "success": False,
                "message": "Sender ID no coincide con el token",
                "error": "sender_id_mismatch"
            }
        except Exception as e:
            print(f"❌ Error al enviar notificación: {str(e)}")
            return {
                "success": False,
                "message": f"Error al enviar notificación: {str(e)}",
                "error": "general_error"
            }
    
    def send_notification_to_user(
        self,
        user_id: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        notification_type: str = "general"
    ) -> Dict:
        """
        Enviar notificación a un usuario específico (busca su FCM token en Firestore)
        
        Args:
            user_id: ID del usuario
            title: Título de la notificación
            body: Cuerpo de la notificación
            data: Datos adicionales (opcional)
            notification_type: Tipo de notificación
            
        Returns:
            Dict con resultado del envío
        """
        try:
            # SIEMPRE guardar notificación en Firestore PRIMERO (historial)
            notification_id = str(uuid.uuid4())
            notification_data = {
                'notification_id': notification_id,
                'user_id': user_id,
                'title': title,
                'body': body,
                'data': data if data else {},
                'type': notification_type,
                'created_at': datetime.utcnow(),
                'is_read': False
            }
            
            self.db.collection('notifications').document(notification_id).set(notification_data)
            print(f"✅ Notificación guardada en Firestore: {notification_id}")
            
            # Intentar obtener FCM token del usuario desde Firestore
            user_doc = self.db.collection('users').document(user_id).get()
            
            if not user_doc.exists:
                print(f"⚠️ Usuario no encontrado: {user_id}")
                return {
                    "success": True,  # Success porque se guardó en Firestore
                    "message": "Notificación guardada (usuario no encontrado para push)",
                    "notification_id": notification_id
                }
            
            user_data = user_doc.to_dict()
            fcm_token = user_data.get('fcm_token')
            
            if not fcm_token:
                print(f"⚠️ Usuario {user_id} no tiene FCM token registrado (notificación guardada)")
                return {
                    "success": True,  # Success porque se guardó en Firestore
                    "message": "Notificación guardada (sin token FCM para push)",
                    "notification_id": notification_id
                }
            
            # Enviar notificación push
            push_result = self.send_notification(
                fcm_token=fcm_token,
                title=title,
                body=body,
                data=data,
                notification_type=notification_type
            )
            
            if push_result["success"]:
                print(f"✅ Notificación push enviada exitosamente")
            else:
                print(f"⚠️ Push falló pero notificación guardada en Firestore")
            
            return {
                "success": True,
                "message": "Notificación guardada y push enviado" if push_result["success"] else "Notificación guardada (push falló)",
                "notification_id": notification_id,
                "push_sent": push_result["success"]
            }
            
        except Exception as e:
            print(f"❌ Error al enviar notificación a usuario: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
    
    def send_notification_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        Enviar notificación a un topic (grupo de usuarios suscritos)
        
        Args:
            topic: Nombre del topic
            title: Título de la notificación
            body: Cuerpo de la notificación
            data: Datos adicionales (opcional)
            
        Returns:
            Dict con resultado del envío
        """
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data if data else {},
                topic=topic,
            )
            
            response = messaging.send(message)
            
            print(f"✅ Notificación enviada al topic '{topic}': {response}")
            
            return {
                "success": True,
                "message": f"Notificación enviada al topic '{topic}'",
                "message_id": response
            }
            
        except Exception as e:
            print(f"❌ Error al enviar notificación al topic: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

# Instancia global del servicio
fcm_service = FCMService()
