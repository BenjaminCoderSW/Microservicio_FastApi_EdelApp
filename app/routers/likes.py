from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.interactions import LikeResponse, LikeStatus
from app.services.firebase_service import firebase_service
from app.services.fcm_service import fcm_service
from app.utils.auth_utils import verify_token
from datetime import datetime
import uuid

router = APIRouter(prefix="/likes", tags=["Likes"])
security = HTTPBearer()

@router.post("/posts/{post_id}", response_model=LikeResponse)
async def like_post(
    post_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Dar like a un post
    
    - Crea documento en colección 'likes'
    - Incrementa contador likes_count en el post
    - Valida que el usuario no haya dado like previamente
    - Valida que el post existe
    - **NUEVO: Envía notificación push al autor del post**
    
    **Header requerido:**
    - Authorization: Bearer {token}
    
    **Respuesta:**
    - Mensaje de éxito
    - ID del post
    - Contador actualizado de likes
    - Estado de like del usuario
    """
    try:
        # Verificar token
        token = credentials.credentials
        current_user = verify_token(token)
        user_id = current_user['uid']
        
        db = firebase_service.get_db()
        
        # 1. VERIFICAR QUE EL POST EXISTE
        post_doc = db.collection('posts').document(post_id).get()
        if not post_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post no encontrado"
            )
        
        post_data = post_doc.to_dict()
        
        # Verificar que el post no esté eliminado
        if post_data.get('is_deleted', False):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post no encontrado"
            )
        
        # 2. VERIFICAR SI EL USUARIO YA DIO LIKE
        existing_like = db.collection('likes')\
            .where('post_id', '==', post_id)\
            .where('user_id', '==', user_id)\
            .limit(1)\
            .get()
        
        if len(list(existing_like)) > 0:
            # El usuario ya dio like a este post
            current_likes = post_data.get('likes_count', 0)
            return LikeResponse(
                message="Ya habías dado like a este post",
                post_id=post_id,
                likes_count=current_likes,
                user_liked=True
            )
        
        # 3. CREAR LIKE
        like_id = str(uuid.uuid4())
        like_data = {
            'like_id': like_id,
            'post_id': post_id,
            'user_id': user_id,
            'created_at': datetime.utcnow()
        }
        
        db.collection('likes').document(like_id).set(like_data)
        
        # 4. INCREMENTAR CONTADOR EN POST
        current_likes = post_data.get('likes_count', 0)
        new_likes_count = current_likes + 1
        
        db.collection('posts').document(post_id).update({
            'likes_count': new_likes_count
        })
        
        print(f"✅ Like agregado: user={user_id}, post={post_id}")
        
        # 5. ENVIAR NOTIFICACIÓN PUSH AL AUTOR DEL POST (si no es el mismo usuario)
        post_author_id = post_data.get('user_id')
        if post_author_id and post_author_id != user_id:
            try:
                # Obtener alias del usuario que dio like
                user_doc = db.collection('users').document(user_id).get()
                user_alias = user_doc.to_dict().get('alias', 'Alguien') if user_doc.exists else 'Alguien'
                
                # Enviar notificación
                fcm_service.send_notification_to_user(
                    user_id=post_author_id,
                    title="❤️ Nuevo like en tu post",
                    body=f"A {user_alias} le gustó tu post",
                    data={
                        "type": "like",
                        "post_id": post_id,
                        "user_id": user_id
                    },
                    notification_type="like"
                )
                print(f"📤 Notificación de like enviada a {post_author_id}")
            except Exception as notif_error:
                # No fallar si la notificación falla
                print(f"⚠️ Error al enviar notificación de like: {str(notif_error)}")
        
        return LikeResponse(
            message="Like agregado exitosamente",
            post_id=post_id,
            likes_count=new_likes_count,
            user_liked=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al agregar like: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al agregar like: {str(e)}"
        )

@router.delete("/posts/{post_id}", response_model=LikeResponse)
async def unlike_post(
    post_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Quitar like de un post
    
    - Elimina documento de colección 'likes'
    - Decrementa contador likes_count en el post
    - Valida que el usuario haya dado like previamente
    - Valida que el post existe
    
    **Header requerido:**
    - Authorization: Bearer {token}
    
    **Respuesta:**
    - Mensaje de éxito
    - ID del post
    - Contador actualizado de likes
    - Estado de like del usuario
    """
    try:
        # Verificar token
        token = credentials.credentials
        current_user = verify_token(token)
        user_id = current_user['uid']
        
        db = firebase_service.get_db()
        
        # 1. VERIFICAR QUE EL POST EXISTE
        post_doc = db.collection('posts').document(post_id).get()
        if not post_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post no encontrado"
            )
        
        post_data = post_doc.to_dict()
        
        # 2. BUSCAR EL LIKE DEL USUARIO
        likes_query = db.collection('likes')\
            .where('post_id', '==', post_id)\
            .where('user_id', '==', user_id)\
            .limit(1)\
            .get()
        
        likes_list = list(likes_query)
        
        if len(likes_list) == 0:
            # El usuario no había dado like
            current_likes = post_data.get('likes_count', 0)
            return LikeResponse(
                message="No habías dado like a este post",
                post_id=post_id,
                likes_count=current_likes,
                user_liked=False
            )
        
        # 3. ELIMINAR LIKE
        like_doc = likes_list[0]
        db.collection('likes').document(like_doc.id).delete()
        
        # 4. DECREMENTAR CONTADOR EN POST
        current_likes = post_data.get('likes_count', 0)
        new_likes_count = max(0, current_likes - 1)  # No permitir números negativos
        
        db.collection('posts').document(post_id).update({
            'likes_count': new_likes_count
        })
        
        print(f"✅ Like eliminado: user={user_id}, post={post_id}")
        
        return LikeResponse(
            message="Like eliminado exitosamente",
            post_id=post_id,
            likes_count=new_likes_count,
            user_liked=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al eliminar like: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar like: {str(e)}"
        )

@router.get("/posts/{post_id}/status", response_model=LikeStatus)
async def get_like_status(
    post_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Obtener estado de like de un post
    
    - Verifica si el usuario dio like al post
    - Retorna contador total de likes
    - Endpoint útil para UI (mostrar corazón lleno/vacío)
    
    **Header requerido:**
    - Authorization: Bearer {token}
    
    **Respuesta:**
    - ID del post
    - Si el usuario dio like (true/false)
    - Total de likes del post
    """
    try:
        # Verificar token
        token = credentials.credentials
        current_user = verify_token(token)
        user_id = current_user['uid']
        
        db = firebase_service.get_db()
        
        # 1. VERIFICAR QUE EL POST EXISTE
        post_doc = db.collection('posts').document(post_id).get()
        if not post_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post no encontrado"
            )
        
        post_data = post_doc.to_dict()
        
        # Verificar que el post no esté eliminado
        if post_data.get('is_deleted', False):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post no encontrado"
            )
        
        # 2. VERIFICAR SI EL USUARIO DIO LIKE
        likes_query = db.collection('likes')\
            .where('post_id', '==', post_id)\
            .where('user_id', '==', user_id)\
            .limit(1)\
            .get()
        
        user_liked = len(list(likes_query)) > 0
        
        # 3. OBTENER CONTADOR DE LIKES
        likes_count = post_data.get('likes_count', 0)
        
        return LikeStatus(
            post_id=post_id,
            user_liked=user_liked,
            likes_count=likes_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al obtener estado de like: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estado de like: {str(e)}"
        )