from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.post import (
    CreatePostRequest, 
    PostResponse, 
    PostListResponse, 
    CreatePostResponse
)
from app.services.firebase_service import firebase_service
from app.services.moderation_service import moderation_service
from app.services.storage_service import storage_service
from app.utils.auth_utils import verify_token
from datetime import datetime
from typing import Optional
import uuid

router = APIRouter(prefix="/posts", tags=["Posts"])
security = HTTPBearer()

@router.post("/", response_model=CreatePostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    request: CreatePostRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Crear un nuevo post
    
    - Valida contenido con moderación automática
    - Si pasa moderación, crea post en Firestore
    - Si incluye imagen, la sube a Storage
    - Rechaza automáticamente contenido inapropiado
    
    **Validaciones:**
    - Contenido máximo 500 caracteres
    - Moderación con 3 APIs: PurgoMalum, ModerateContent, OpenAI
    - Imagen opcional, máximo 5MB
    
    **Header requerido:**
    - Authorization: Bearer {token}
    """
    try:
        token = credentials.credentials
        current_user = verify_token(token)
        
        # 1. MODERACIÓN DE CONTENIDO
        print(f"🔍 Moderando contenido del post...")
        moderation_result = moderation_service.moderate_content(request.content)
        
        if not moderation_result.is_safe:
            print(f"❌ Contenido rechazado por: {', '.join(moderation_result.flagged_by)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Contenido rechazado por moderación automática",
                    "reason": moderation_result.reason,
                    "flagged_by": moderation_result.flagged_by
                }
            )
        
        print(f"✅ Contenido aprobado por moderación")
        
        # 2. CREAR POST EN FIRESTORE
        db = firebase_service.get_db()
        post_id = str(uuid.uuid4())
        
        # Obtener alias del usuario
        user_doc = db.collection('users').document(current_user['uid']).get()
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        user_data = user_doc.to_dict()
        alias = user_data['alias']
        
        # Datos del post
        post_data = {
            'post_id': post_id,
            'user_id': current_user['uid'],
            'alias': alias,
            'content': request.content,
            'image_url': request.image_url,
            'created_at': datetime.utcnow(),
            'likes_count': 0,
            'comments_count': 0,
            'is_deleted': False,
            'moderation_passed': True,
            'moderation_flagged_by': []
        }
        
        # Guardar en Firestore
        db.collection('posts').document(post_id).set(post_data)
        
        print(f"✅ Post creado: {post_id} por usuario {current_user['uid']}")
        
        return CreatePostResponse(
            message="Post creado exitosamente",
            post_id=post_id,
            moderation_status="approved"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al crear post: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear post: {str(e)}"
        )

@router.post("/upload", response_model=CreatePostResponse, status_code=status.HTTP_201_CREATED)
async def create_post_with_image(
    content: str = Form(..., min_length=1, max_length=500),
    image: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Crear post con imagen
    
    - Sube imagen a Firebase Storage
    - Modera contenido del texto
    - Crea post en Firestore
    
    **Validaciones:**
    - Contenido máximo 500 caracteres
    - Imagen máximo 5MB
    - Tipos permitidos: JPG, PNG, GIF, WEBP
    
    **Header requerido:**
    - Authorization: Bearer {token}
    """
    try:
        token = credentials.credentials
        current_user = verify_token(token)
        
        # 1. VALIDAR TIPO DE IMAGEN
        if not image.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo debe ser una imagen"
            )
        
        # 2. LEER IMAGEN
        image_data = await image.read()
        
        # Validar tamaño (5MB)
        if len(image_data) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La imagen no puede ser mayor a 5MB"
            )
        
        # 3. MODERACIÓN DE CONTENIDO
        print(f"🔍 Moderando contenido del post...")
        moderation_result = moderation_service.moderate_content(content)
        
        if not moderation_result.is_safe:
            print(f"❌ Contenido rechazado por: {', '.join(moderation_result.flagged_by)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Contenido rechazado por moderación automática",
                    "reason": moderation_result.reason,
                    "flagged_by": moderation_result.flagged_by
                }
            )
        
        print(f"✅ Contenido aprobado por moderación")
        
        # 4. SUBIR IMAGEN A STORAGE
        print(f"📤 Subiendo imagen a Storage...")
        image_url = storage_service.upload_post_image(image_data, current_user['uid'])
        
        # 5. MODERAR IMAGEN
        print(f"🔍 Moderando imagen subida...")
        image_moderation = moderation_service.moderate_image(image_url)
        
        if not image_moderation.is_safe:
            # Eliminar imagen del storage
            storage_service.delete_image(image_url)
            print(f"❌ Imagen rechazada y eliminada: {', '.join(image_moderation.flagged_by)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Imagen rechazada por moderación automática",
                    "reason": image_moderation.reason,
                    "flagged_by": image_moderation.flagged_by
                }
            )
        
        print(f"✅ Imagen aprobada por moderación")
        
        # 5. CREAR POST EN FIRESTORE
        db = firebase_service.get_db()
        post_id = str(uuid.uuid4())
        
        # Obtener alias del usuario
        user_doc = db.collection('users').document(current_user['uid']).get()
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        user_data = user_doc.to_dict()
        alias = user_data['alias']
        
        # Datos del post
        post_data = {
            'post_id': post_id,
            'user_id': current_user['uid'],
            'alias': alias,
            'content': content,
            'image_url': image_url,
            'created_at': datetime.utcnow(),
            'likes_count': 0,
            'comments_count': 0,
            'is_deleted': False,
            'moderation_passed': True,
            'moderation_flagged_by': []
        }
        
        # Guardar en Firestore
        db.collection('posts').document(post_id).set(post_data)
        
        print(f"✅ Post con imagen creado: {post_id}")
        
        return CreatePostResponse(
            message="Post con imagen creado exitosamente",
            post_id=post_id,
            moderation_status="approved"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al crear post con imagen: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear post con imagen: {str(e)}"
        )

@router.get("/", response_model=PostListResponse)
async def get_posts_feed(
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=1, le=100, description="Posts por página")
):
    """
    Obtener feed de posts
    
    - Endpoint público (no requiere autenticación)
    - Retorna posts ordenados por fecha (más recientes primero)
    - Paginación incluida
    - No incluye posts eliminados
    
    **Parámetros:**
    - page: Número de página (default: 1)
    - page_size: Posts por página (default: 20, max: 100)
    """
    try:
        db = firebase_service.get_db()
        
        # Query base: posts no eliminados, ordenados por fecha descendente
        query = db.collection('posts').where('is_deleted', '==', False).order_by('created_at', direction='DESCENDING')
        
        # Obtener todos los posts (para contar total)
        all_posts = list(query.stream())
        total = len(all_posts)
        
        # Calcular offset para paginación
        offset = (page - 1) * page_size
        
        # Obtener posts de la página actual
        posts_page = all_posts[offset:offset + page_size]
        
        # Convertir a PostResponse
        posts_list = []
        for post_doc in posts_page:
            post_data = post_doc.to_dict()
            posts_list.append(PostResponse(
                post_id=post_data['post_id'],
                user_id=post_data['user_id'],
                alias=post_data['alias'],
                content=post_data['content'],
                image_url=post_data.get('image_url'),
                created_at=post_data['created_at'],
                likes_count=post_data.get('likes_count', 0),
                comments_count=post_data.get('comments_count', 0),
                is_deleted=post_data.get('is_deleted', False)
            ))
        
        # Verificar si hay más páginas
        has_more = (offset + page_size) < total
        
        print(f"✅ Feed obtenido: página {page}, {len(posts_list)} posts")
        
        return PostListResponse(
            posts=posts_list,
            total=total,
            page=page,
            page_size=page_size,
            has_more=has_more
        )
        
    except Exception as e:
        print(f"❌ Error al obtener feed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener feed: {str(e)}"
        )

@router.get("/{post_id}", response_model=PostResponse)
async def get_post_by_id(post_id: str):
    """
    Obtener post individual por ID
    
    - Endpoint público (no requiere autenticación)
    - Retorna detalles completos del post
    - Incluye contadores de likes y comentarios
    
    **Parámetros:**
    - post_id: ID del post a obtener
    """
    try:
        db = firebase_service.get_db()
        
        # Obtener post
        post_doc = db.collection('posts').document(post_id).get()
        
        if not post_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post no encontrado"
            )
        
        post_data = post_doc.to_dict()
        
        # Verificar si está eliminado
        if post_data.get('is_deleted', False):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post no encontrado"
            )
        
        print(f"✅ Post obtenido: {post_id}")
        
        return PostResponse(
            post_id=post_data['post_id'],
            user_id=post_data['user_id'],
            alias=post_data['alias'],
            content=post_data['content'],
            image_url=post_data.get('image_url'),
            created_at=post_data['created_at'],
            likes_count=post_data.get('likes_count', 0),
            comments_count=post_data.get('comments_count', 0),
            is_deleted=post_data.get('is_deleted', False)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al obtener post: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener post: {str(e)}"
        )

@router.delete("/{post_id}")
async def delete_post(
    post_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Eliminar post (soft delete)
    
    - Solo el creador del post puede eliminarlo
    - Soft delete: marca is_deleted = True
    - No elimina físicamente el post de la BD
    
    **Header requerido:**
    - Authorization: Bearer {token}
    """
    try:
        token = credentials.credentials
        current_user = verify_token(token)
        
        db = firebase_service.get_db()
        
        # Obtener post
        post_doc = db.collection('posts').document(post_id).get()
        
        if not post_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post no encontrado"
            )
        
        post_data = post_doc.to_dict()
        
        # Verificar que el usuario sea el creador del post
        if post_data['user_id'] != current_user['uid']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para eliminar este post"
            )
        
        # Soft delete
        db.collection('posts').document(post_id).update({
            'is_deleted': True,
            'deleted_at': datetime.utcnow()
        })
        
        print(f"✅ Post eliminado (soft delete): {post_id}")
        
        return {
            "message": "Post eliminado exitosamente",
            "post_id": post_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al eliminar post: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar post: {str(e)}"
        )