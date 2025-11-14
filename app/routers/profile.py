from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from app.services.firebase_service import firebase_service
from app.utils.auth_utils import verify_token
from firebase_admin import auth

router = APIRouter(prefix="/profile", tags=["Profile"])
security = HTTPBearer()

# ==================== MODELOS ====================

class ProfileResponse(BaseModel):
    """Modelo para respuesta de perfil"""
    user_id: str
    email: str
    alias: str
    created_at: datetime
    is_admin: bool = False
    profile_image: Optional[str] = None
    fcm_token: Optional[str] = None  # NUEVO: Incluir en respuesta (opcional)
    posts_count: int = 0
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "abc123xyz",
                "email": "usuario@ejemplo.com",
                "alias": "UsuarioAnonimo",
                "created_at": "2024-10-13T10:30:00",
                "is_admin": False,
                "profile_image": "https://storage.googleapis.com/...",
                "fcm_token": "dXpZL3J2k4z...",
                "posts_count": 5
            }
        }

class UpdateProfileRequest(BaseModel):
    """Modelo para actualizar perfil"""
    alias: Optional[str] = Field(None, min_length=3, max_length=50, description="Nuevo alias (opcional)")
    profile_image: Optional[str] = Field(None, description="URL de imagen de perfil (opcional)")
    fcm_token: Optional[str] = Field(None, description="Token FCM del dispositivo para notificaciones push (opcional)")
    
    @validator('alias')
    def validate_alias(cls, v):
        if v is not None:
            # Eliminar espacios al inicio y final
            v = v.strip()
            
            # Validar longitud después de eliminar espacios
            if len(v) < 3:
                raise ValueError('El alias debe tener al menos 3 caracteres')
            if len(v) > 50:
                raise ValueError('El alias no puede tener más de 50 caracteres')
            
            # Permitir letras, números, espacios, guiones y guiones bajos
            # Remover espacios temporalmente para validar caracteres
            alias_sin_espacios = v.replace(' ', '').replace('_', '').replace('-', '')
            
            if not alias_sin_espacios.isalnum():
                raise ValueError('El alias solo puede contener letras, números, espacios, guiones y guiones bajos')
            
            # No permitir espacios múltiples consecutivos
            if '  ' in v:
                raise ValueError('El alias no puede tener espacios múltiples consecutivos')
        
        return v
    
    @validator('profile_image')
    def validate_profile_image(cls, v):
        if v is not None and v != "":
            # Validar que sea una URL válida (básico)
            if not v.startswith(('http://', 'https://')):
                raise ValueError('La imagen de perfil debe ser una URL válida')
        return v
    
    @validator('fcm_token')
    def validate_fcm_token(cls, v):
        if v is not None and v != "":
            # Validar que no esté vacío y tenga longitud razonable
            if len(v) < 50:
                raise ValueError('Token FCM inválido (demasiado corto)')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "alias": "Nuevo Alias Con Espacios",
                "profile_image": "https://storage.googleapis.com/bucket/image.jpg",
                "fcm_token": "dXpZL3J2k4zNhMw1hGkhYb4lrZRki1FuCbNLGAvSh8dXpZL3..."
            }
        }

class UpdateProfileResponse(BaseModel):
    """Modelo para respuesta de actualización de perfil"""
    message: str
    user_id: str
    updated_fields: list[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Perfil actualizado exitosamente",
                "user_id": "abc123xyz",
                "updated_fields": ["alias", "profile_image", "fcm_token"]
            }
        }

# ==================== ENDPOINTS ====================

@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Obtener mi perfil
    
    - Retorna información del perfil del usuario autenticado
    - Incluye contador de posts publicados
    - Incluye FCM token si está registrado
    
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
        
        # Contar posts del usuario
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
            fcm_token=user_data.get('fcm_token'),  # NUEVO: Incluir FCM token
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
    - NO incluye FCM token (privado)
    
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
        
        # Contar posts del usuario
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
            fcm_token=None,  # NO exponer FCM token públicamente
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
    
    - Permite actualizar alias, foto de perfil y FCM token
    - Solo el usuario autenticado puede actualizar su propio perfil
    - Todos los campos son opcionales
    - **IMPORTANTE: Alias puede contener espacios, números, guiones y guiones bajos**
    
    **Campos actualizables:**
    - alias: Nuevo nombre de usuario (3-50 caracteres, permite espacios)
    - profile_image: URL de nueva imagen de perfil
    - fcm_token: Token FCM del dispositivo para notificaciones push
    
    **Header requerido:**
    - Authorization: Bearer {token}
    
    **Nota sobre fcm_token:**
    Este campo es usado por la app Android/iOS para registrar el dispositivo
    y recibir notificaciones push. Debe ser enviado cada vez que:
    - Usuario hace login
    - Token FCM se renueva
    - Usuario instala la app en un nuevo dispositivo
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
        
        # NUEVO: Actualizar FCM token
        if request.fcm_token is not None:
            update_data['fcm_token'] = request.fcm_token
            updated_fields.append('fcm_token')
            print(f"🔔 FCM token actualizado para usuario: {current_user['uid']}")
        
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