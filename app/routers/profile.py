from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.profile import ProfileResponse, UpdateProfileRequest, UpdateProfileResponse
from app.services.firebase_service import firebase_service
from app.utils.auth_utils import verify_token
from firebase_admin import auth
from datetime import datetime

router = APIRouter(prefix="/profile", tags=["Profile"])
security = HTTPBearer()

@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Obtener mi perfil
    
    - Retorna información del perfil del usuario autenticado
    - Incluye contador de posts publicados
    
    **Header requerido:**
    - Authorization: Bearer {token}
    """
    try:
        token = credentials.credentials
        current_user = verify_token(token)
        
        db = firebase_service.get_db()
        
        # Obtener datos del usuario
        user_doc = db.collection('users').document(current_user['uid']).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        user_data = user_doc.to_dict()
        
        # Contar posts del usuario (por ahora 0, hasta que implementemos posts)
        posts_count = 0
        try:
            posts_query = db.collection('posts').where('user_id', '==', current_user['uid']).stream()
            posts_count = len(list(posts_query))
        except Exception as e:
            print(f"⚠️ No se pudo contar posts: {str(e)}")
            posts_count = 0
        
        print(f"✅ Perfil obtenido: {current_user['uid']}")
        
        return ProfileResponse(
            user_id=current_user['uid'],
            email=user_data['email'],
            alias=user_data['alias'],
            created_at=user_data['created_at'],
            is_admin=user_data.get('is_admin', False),
            profile_image=user_data.get('profile_image'),
            posts_count=posts_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al obtener perfil: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener perfil: {str(e)}"
        )

@router.get("/{user_id}", response_model=ProfileResponse)
async def get_user_profile(user_id: str):
    """
    Obtener perfil de un usuario específico
    
    - Endpoint público (no requiere autenticación)
    - Retorna información básica del perfil
    - Incluye contador de posts publicados
    
    **Parámetros:**
    - user_id: ID del usuario a consultar
    """
    try:
        db = firebase_service.get_db()
        
        # Obtener datos del usuario
        user_doc = db.collection('users').document(user_id).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        user_data = user_doc.to_dict()
        
        # Contar posts del usuario (por ahora 0, hasta que implementemos posts)
        posts_count = 0
        try:
            posts_query = db.collection('posts').where('user_id', '==', user_id).stream()
            posts_count = len(list(posts_query))
        except Exception as e:
            print(f"⚠️ No se pudo contar posts: {str(e)}")
            posts_count = 0
        
        print(f"✅ Perfil público obtenido: {user_id}")
        
        return ProfileResponse(
            user_id=user_id,
            email=user_data['email'],
            alias=user_data['alias'],
            created_at=user_data['created_at'],
            is_admin=user_data.get('is_admin', False),
            profile_image=user_data.get('profile_image'),
            posts_count=posts_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al obtener perfil público: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener perfil público: {str(e)}"
        )

@router.put("/me", response_model=UpdateProfileResponse)
async def update_my_profile(
    request: UpdateProfileRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Actualizar mi perfil
    
    - Permite actualizar alias y foto de perfil
    - Solo el usuario autenticado puede actualizar su propio perfil
    - Todos los campos son opcionales
    
    **Campos actualizables:**
    - alias: Nuevo nombre de usuario (3-20 caracteres)
    - profile_image: URL de nueva imagen de perfil
    
    **Header requerido:**
    - Authorization: Bearer {token}
    """
    try:
        token = credentials.credentials
        current_user = verify_token(token)
        
        db = firebase_service.get_db()
        user_ref = db.collection('users').document(current_user['uid'])
        
        # Verificar que el usuario existe
        user_doc = user_ref.get()
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        # Preparar datos a actualizar
        update_data = {}
        updated_fields = []
        
        if request.alias is not None:
            update_data['alias'] = request.alias
            updated_fields.append('alias')
            
            # Actualizar también en Firebase Auth
            try:
                auth.update_user(current_user['uid'], display_name=request.alias)
            except Exception as e:
                print(f"⚠️ No se pudo actualizar alias en Firebase Auth: {str(e)}")
        
        if request.profile_image is not None:
            update_data['profile_image'] = request.profile_image
            updated_fields.append('profile_image')
        
        # Si no hay nada que actualizar
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe proporcionar al menos un campo para actualizar"
            )
        
        # Agregar timestamp de actualización
        update_data['updated_at'] = datetime.utcnow()
        
        # Actualizar en Firestore
        user_ref.update(update_data)
        
        print(f"✅ Perfil actualizado: {current_user['uid']} - Campos: {updated_fields}")
        
        return UpdateProfileResponse(
            message="Perfil actualizado exitosamente",
            user_id=current_user['uid'],
            updated_fields=updated_fields
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al actualizar perfil: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar perfil: {str(e)}"
        )