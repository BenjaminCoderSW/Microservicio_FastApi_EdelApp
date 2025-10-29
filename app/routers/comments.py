from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.interactions import (
    CreateCommentRequest, 
    CommentResponse, 
    CommentListResponse
)
from app.services.firebase_service import firebase_service
from app.services.fcm_service import fcm_service
from app.utils.auth_utils import verify_token
from datetime import datetime
import uuid
from typing import Optional

router = APIRouter(prefix="/comments", tags=["Comments"])
security = HTTPBearer()

@router.post("/posts/{post_id}", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    post_id: str,
    request: CreateCommentRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Crear comentario en un post
    
    - Crea documento en colección 'comments'
    - Incrementa contador comments_count en el post
    - Valida longitud del comentario (1-500 caracteres)
    - Valida que el post existe
    - **NUEVO: Envía notificación push al autor del post**
    
    **Header requerido:**
    - Authorization: Bearer {token}
    
    **Body:**
    - content: Texto del comentario (1-500 caracteres)
    
    **Respuesta:**
    - Datos completos del comentario creado
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
        
        # 2. OBTENER DATOS DEL USUARIO
        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        user_data = user_doc.to_dict()
        alias = user_data['alias']
        
        # 3. CREAR COMENTARIO
        comment_id = str(uuid.uuid4())
        comment_data = {
            'comment_id': comment_id,
            'post_id': post_id,
            'user_id': user_id,
            'alias': alias,
            'content': request.content,
            'created_at': datetime.utcnow(),
            'is_deleted': False
        }
        
        db.collection('comments').document(comment_id).set(comment_data)
        
        # 4. INCREMENTAR CONTADOR EN POST
        current_comments = post_data.get('comments_count', 0)
        new_comments_count = current_comments + 1
        
        db.collection('posts').document(post_id).update({
            'comments_count': new_comments_count
        })
        
        print(f"✅ Comentario creado: {comment_id} en post {post_id}")
        
        # 5. ENVIAR NOTIFICACIÓN PUSH AL AUTOR DEL POST (si no es el mismo usuario)
        post_author_id = post_data.get('user_id')
        if post_author_id and post_author_id != user_id:
            try:
                # Enviar notificación
                fcm_service.send_notification_to_user(
                    user_id=post_author_id,
                    title="💬 Nuevo comentario en tu post",
                    body=f"{alias} comentó: {request.content[:50]}{'...' if len(request.content) > 50 else ''}",
                    data={
                        "type": "comment",
                        "post_id": post_id,
                        "comment_id": comment_id,
                        "user_id": user_id
                    },
                    notification_type="comment"
                )
                print(f"📤 Notificación de comentario enviada a {post_author_id}")
            except Exception as notif_error:
                # No fallar si la notificación falla
                print(f"⚠️ Error al enviar notificación de comentario: {str(notif_error)}")
        
        return CommentResponse(
            comment_id=comment_id,
            post_id=post_id,
            user_id=user_id,
            alias=alias,
            content=request.content,
            created_at=comment_data['created_at'],
            is_deleted=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al crear comentario: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear comentario: {str(e)}"
        )

@router.get("/posts/{post_id}", response_model=CommentListResponse)
async def get_comments(
    post_id: str,
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=1, le=100, description="Comentarios por página")
):
    """
    Obtener comentarios de un post (paginado)
    
    - Endpoint público (no requiere autenticación)
    - Retorna comentarios ordenados por fecha (más recientes primero)
    - Paginación incluida
    - No incluye comentarios eliminados
    
    **Parámetros:**
    - page: Número de página (default: 1)
    - page_size: Comentarios por página (default: 20, max: 100)
    
    **Respuesta:**
    - Lista de comentarios
    - Total de comentarios
    - Info de paginación
    """
    try:
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
        
        # 2. OBTENER COMENTARIOS (ordenados por fecha descendente)
        query = db.collection('comments')\
            .where('post_id', '==', post_id)\
            .where('is_deleted', '==', False)\
            .order_by('created_at', direction='DESCENDING')
        
        # Obtener todos los comentarios (para contar total)
        all_comments = list(query.stream())
        total = len(all_comments)
        
        # 3. APLICAR PAGINACIÓN
        offset = (page - 1) * page_size
        comments_page = all_comments[offset:offset + page_size]
        
        # 4. CONVERTIR A CommentResponse
        comments_list = []
        for comment_doc in comments_page:
            comment_data = comment_doc.to_dict()
            comments_list.append(CommentResponse(
                comment_id=comment_data['comment_id'],
                post_id=comment_data['post_id'],
                user_id=comment_data['user_id'],
                alias=comment_data['alias'],
                content=comment_data['content'],
                created_at=comment_data['created_at'],
                is_deleted=comment_data.get('is_deleted', False)
            ))
        
        # 5. VERIFICAR SI HAY MÁS PÁGINAS
        has_more = (offset + page_size) < total
        
        print(f"✅ Comentarios obtenidos: post={post_id}, página={page}, total={len(comments_list)}")
        
        return CommentListResponse(
            comments=comments_list,
            total=total,
            page=page,
            page_size=page_size,
            has_more=has_more
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al obtener comentarios: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener comentarios: {str(e)}"
        )

@router.delete("/{comment_id}")
async def delete_comment(
    comment_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Eliminar comentario (soft delete)
    
    - Solo el autor del comentario puede eliminarlo
    - Soft delete: marca is_deleted = True
    - Decrementa contador comments_count en el post
    - No elimina físicamente el comentario
    
    **Header requerido:**
    - Authorization: Bearer {token}
    
    **Respuesta:**
    - Mensaje de éxito
    """
    try:
        # Verificar token
        token = credentials.credentials
        current_user = verify_token(token)
        user_id = current_user['uid']
        
        db = firebase_service.get_db()
        
        # 1. OBTENER COMENTARIO
        comment_doc = db.collection('comments').document(comment_id).get()
        
        if not comment_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comentario no encontrado"
            )
        
        comment_data = comment_doc.to_dict()
        
        # Verificar si ya está eliminado
        if comment_data.get('is_deleted', False):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comentario no encontrado"
            )
        
        # 2. VERIFICAR QUE EL USUARIO ES EL AUTOR
        if comment_data['user_id'] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para eliminar este comentario"
            )
        
        # 3. SOFT DELETE DEL COMENTARIO
        db.collection('comments').document(comment_id).update({
            'is_deleted': True,
            'deleted_at': datetime.utcnow()
        })
        
        # 4. DECREMENTAR CONTADOR EN POST
        post_id = comment_data['post_id']
        post_doc = db.collection('posts').document(post_id).get()
        
        if post_doc.exists:
            post_data = post_doc.to_dict()
            current_comments = post_data.get('comments_count', 0)
            new_comments_count = max(0, current_comments - 1)
            
            db.collection('posts').document(post_id).update({
                'comments_count': new_comments_count
            })
        
        print(f"✅ Comentario eliminado (soft delete): {comment_id}")
        
        return {
            "message": "Comentario eliminado exitosamente",
            "comment_id": comment_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al eliminar comentario: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar comentario: {str(e)}"
        )

@router.get("/{comment_id}", response_model=CommentResponse)
async def get_comment(comment_id: str):
    """
    Obtener comentario específico por ID
    
    - Endpoint público (no requiere autenticación)
    - Retorna detalles completos del comentario
    - Útil para enlaces directos a comentarios
    
    **Parámetros:**
    - comment_id: ID del comentario
    
    **Respuesta:**
    - Datos completos del comentario
    """
    try:
        db = firebase_service.get_db()
        
        # OBTENER COMENTARIO
        comment_doc = db.collection('comments').document(comment_id).get()
        
        if not comment_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comentario no encontrado"
            )
        
        comment_data = comment_doc.to_dict()
        
        # Verificar si está eliminado
        if comment_data.get('is_deleted', False):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comentario no encontrado"
            )
        
        print(f"✅ Comentario obtenido: {comment_id}")
        
        return CommentResponse(
            comment_id=comment_data['comment_id'],
            post_id=comment_data['post_id'],
            user_id=comment_data['user_id'],
            alias=comment_data['alias'],
            content=comment_data['content'],
            created_at=comment_data['created_at'],
            is_deleted=comment_data.get('is_deleted', False)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al obtener comentario: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener comentario: {str(e)}"
        )