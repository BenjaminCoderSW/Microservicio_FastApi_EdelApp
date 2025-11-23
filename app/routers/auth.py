from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.user import RegisterRequest, LoginRequest, LoginResponse, ChangePasswordRequest, ChangePasswordResponse
from app.services.firebase_service import firebase_service
from app.services.datadog_service import DatadogService, track_execution_time
from app.utils.auth_utils import create_access_token, verify_token, invalidate_token
from firebase_admin import auth
from datetime import datetime
import requests
from app.config import settings
from typing import Optional

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()

@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
@track_execution_time("auth.register.duration")  # ✅ NUEVO
async def register(request: RegisterRequest):
    """
    Registrar nuevo usuario
    
    - Valida que el email sea único
    - Crea usuario en Firebase Auth
    - Crea documento en Firestore colección 'users'
    - Retorna token JWT válido por 24 horas
    
    **Validaciones:**
    - Email válido y único
    - Contraseña mínimo 6 caracteres
    - Alias entre 3-20 caracteres
    """
    try:
        # ✅ NUEVO: Contador de intentos de registro
        DatadogService.increment_counter(
            "auth.register.attempts", 
            tags=["endpoint:/auth/register"]
        )
        
        # Verificar si el email ya existe
        try:
            existing_user = auth.get_user_by_email(request.email)
            # ✅ NUEVO: Email duplicado
            DatadogService.increment_counter(
                "auth.register.failed", 
                tags=["endpoint:/auth/register", "reason:email_exists"]
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )
        except auth.UserNotFoundError:
            pass
        
        # Crear usuario en Firebase Auth
        user = auth.create_user(
            email=request.email,
            password=request.password,
            display_name=request.alias
        )
        
        print(f"✅ Usuario creado en Firebase Auth: {user.uid}")
        
        # Crear documento en Firestore
        db = firebase_service.get_db()
        user_data = {
            'uid': user.uid,
            'email': request.email,
            'alias': request.alias,
            'created_at': datetime.utcnow(),
            'is_admin': False,
            'profile_image': None
        }
        
        db.collection('users').document(user.uid).set(user_data)
        print(f"✅ Usuario creado en Firestore: {user.uid}")
        
        # Generar token JWT
        token_data = {
            'uid': user.uid,
            'email': request.email,
            'alias': request.alias
        }
        token = create_access_token(token_data)
        
        # ✅ NUEVO: Registro exitoso
        DatadogService.increment_counter(
            "auth.register.success", 
            tags=["endpoint:/auth/register"]
        )
        
        # ✅ NUEVO: Gauge de usuarios totales
        total_users = len(list(db.collection('users').stream()))
        DatadogService.gauge(
            "users.total_count", 
            total_users,
            tags=["type:registered"]
        )
        
        return LoginResponse(
            token=token,
            user_id=user.uid,
            alias=request.alias,
            email=request.email,
            is_admin=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en registro: {str(e)}")
        # ✅ NUEVO: Error inesperado
        DatadogService.increment_counter(
            "auth.register.error",
            tags=["endpoint:/auth/register", f"error_type:{type(e).__name__}"]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar usuario: {str(e)}"
        )

@router.post("/login", response_model=LoginResponse)
@track_execution_time("auth.login.duration")  # ✅ NUEVO
async def login(request: LoginRequest):
    """
    Autenticar usuario
    
    - Verifica credenciales con Firebase Auth
    - Obtiene datos adicionales de Firestore
    - Genera token JWT válido por 24 horas
    
    **Credenciales requeridas:**
    - Email registrado
    - Contraseña correcta
    """
    try:
        # ✅ NUEVO: Contador de intentos
        DatadogService.increment_counter(
            "auth.login.attempts", 
            tags=["endpoint:/auth/login"]
        )
        
        # Verificar credenciales con Firebase REST API
        verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={settings.firebase_web_api_key}"
        payload = {
            "email": request.email,
            "password": request.password,
            "returnSecureToken": True
        }
        
        response = requests.post(verify_url, json=payload)
        
        if response.status_code != 200:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message', 'Credenciales inválidas')
            
            # ✅ NUEVO: Login fallido
            DatadogService.increment_counter(
                "auth.login.failed",
                tags=["endpoint:/auth/login", f"reason:{error_message}"]
            )
            
            if error_message == "EMAIL_NOT_FOUND":
                detail = "Email no registrado"
            elif error_message == "INVALID_PASSWORD":
                detail = "Contraseña incorrecta"
            elif error_message == "USER_DISABLED":
                detail = "Usuario deshabilitado"
            else:
                detail = "Credenciales inválidas"
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=detail
            )
        
        # Obtener UID del usuario
        auth_data = response.json()
        uid = auth_data['localId']
        
        # Obtener datos del usuario desde Firestore
        db = firebase_service.get_db()
        user_doc = db.collection('users').document(uid).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado en la base de datos"
            )
        
        user_data = user_doc.to_dict()
        
        print(f"✅ Login exitoso: {uid}")
        
        # Generar token JWT
        token_data = {
            'uid': uid,
            'email': request.email,
            'alias': user_data['alias'],
            'is_admin': user_data.get('is_admin', False)
        }
        token = create_access_token(token_data)
        
        # ✅ NUEVO: Login exitoso
        DatadogService.increment_counter(
            "auth.login.success", 
            tags=["endpoint:/auth/login", "method:password"]
        )
        
        return LoginResponse(
            token=token,
            user_id=uid,
            alias=user_data['alias'],
            email=request.email,
            is_admin=user_data.get('is_admin', False)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en login: {str(e)}")
        # ✅ NUEVO: Error inesperado
        DatadogService.increment_counter(
            "auth.login.error",
            tags=["endpoint:/auth/login", f"error_type:{type(e).__name__}"]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al iniciar sesión: {str(e)}"
        )

@router.post("/logout")
@track_execution_time("auth.logout.duration")  # ✅ NUEVO
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Cerrar sesión
    
    - Invalida el token actual agregándolo a blacklist
    - Requiere token JWT válido en header Authorization
    
    **Header requerido:**
    - Authorization: Bearer {token}
    """
    try:
        token = credentials.credentials
        payload = verify_token(token)
        invalidate_token(token)
        
        print(f"✅ Logout exitoso: {payload.get('uid')}")
        
        # ✅ NUEVO: Logout exitoso
        DatadogService.increment_counter(
            "auth.logout.success", 
            tags=["endpoint:/auth/logout"]
        )
        
        return {
            "message": "Sesión cerrada exitosamente",
            "user_id": payload.get('uid')
        }
        
    except Exception as e:
        print(f"❌ Error en logout: {str(e)}")
        # ✅ NUEVO: Error en logout
        DatadogService.increment_counter(
            "auth.logout.error",
            tags=["endpoint:/auth/logout", f"error_type:{type(e).__name__}"]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al cerrar sesión: {str(e)}"
        )

@router.delete("/account", status_code=status.HTTP_200_OK)
async def delete_account(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Eliminar cuenta del usuario autenticado
    
    - Elimina el usuario de Firebase Authentication
    - Elimina el documento del usuario en Firestore (colección 'users')
    - Elimina todos los posts creados por el usuario (colección 'posts')
    - Invalida el token JWT del usuario
    
    **Header requerido:**
    - Authorization: Bearer {token}
    
    **Respuesta:**
    - Mensaje de confirmación
    
    **NOTA:** Esta acción es irreversible y eliminará permanentemente:
    - La cuenta del usuario
    - Todos los posts creados por el usuario
    - El acceso con el token actual
    """
    try:
        # Verificar token
        token = credentials.credentials
        current_user = verify_token(token)
        user_id = current_user['uid']
        
        print(f"🗑️ Iniciando eliminación de cuenta para usuario: {user_id}")
        
        db = firebase_service.get_db()
        
        # PASO 1: Verificar que el usuario existe
        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        user_data = user_doc.to_dict()
        user_alias = user_data.get('alias', 'Usuario')
        
        # PASO 2: Eliminar todos los posts del usuario
        posts_query = db.collection('posts').where('user_id', '==', user_id)
        posts_docs = list(posts_query.stream())
        posts_count = len(posts_docs)
        
        for post_doc in posts_docs:
            post_doc.reference.delete()
        
        print(f"✅ Eliminados {posts_count} posts del usuario {user_id}")
        
        # PASO 3: Eliminar documento del usuario en Firestore
        db.collection('users').document(user_id).delete()
        print(f"✅ Documento de usuario eliminado de Firestore: {user_id}")
        
        # PASO 4: Eliminar usuario de Firebase Authentication
        try:
            auth.delete_user(user_id)
            print(f"✅ Usuario eliminado de Firebase Auth: {user_id}")
        except auth.UserNotFoundError:
            print(f"⚠️ Usuario no encontrado en Firebase Auth (ya eliminado): {user_id}")
        
        # PASO 5: Invalidar el token JWT
        invalidate_token(token)
        print(f"✅ Token JWT invalidado para usuario: {user_id}")
        
        return {
            "message": f"Cuenta de '{user_alias}' eliminada exitosamente",
            "user_id": user_id,
            "posts_deleted": posts_count,
            "details": {
                "account_deleted": True,
                "posts_deleted": posts_count,
                "token_invalidated": True
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al eliminar cuenta: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar cuenta: {str(e)}"
        )

@router.get("/me")
async def get_current_user_info(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Obtener información del usuario actual
    
    - Retorna datos del usuario autenticado
    - Requiere token JWT válido
    
    **Header requerido:**
    - Authorization: Bearer {token}
    """
    try:
        token = credentials.credentials
        current_user = verify_token(token)
        
        db = firebase_service.get_db()
        user_doc = db.collection('users').document(current_user['uid']).get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        user_data = user_doc.to_dict()
        
        return {
            "user_id": current_user['uid'],
            "email": user_data['email'],
            "alias": user_data['alias'],
            "is_admin": user_data.get('is_admin', False),
            "created_at": user_data['created_at'],
            "profile_image": user_data.get('profile_image')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al obtener usuario: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener información del usuario: {str(e)}"
        )
        
@router.put("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    request: ChangePasswordRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Cambiar contraseña del usuario autenticado
    
    - Valida que la contraseña actual sea correcta
    - Actualiza la contraseña en Firebase Auth
    - Requiere que el usuario esté autenticado
    - Nueva contraseña debe tener mínimo 6 caracteres
    
    **Header requerido:**
    - Authorization: Bearer {token}
    
    **Body:**
    - current_password: Contraseña actual
    - new_password: Nueva contraseña (mínimo 6 caracteres)
    
    **Respuesta:**
    - Mensaje de confirmación
    - ID del usuario
    
    **IMPORTANTE:** 
    - El token JWT actual seguirá siendo válido después del cambio
    - El usuario NO necesita volver a iniciar sesión
    """
    try:
        # Verificar token
        token = credentials.credentials
        current_user = verify_token(token)
        user_id = current_user['uid']
        email = current_user['email']
        
        print(f"🔐 Iniciando cambio de contraseña para usuario: {user_id}")
        
        # PASO 1: Verificar que la contraseña actual sea correcta
        verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={settings.firebase_web_api_key}"
        payload = {
            "email": email,
            "password": request.current_password,
            "returnSecureToken": False
        }
        
        response = requests.post(verify_url, json=payload)
        
        if response.status_code != 200:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message', 'Contraseña actual incorrecta')
            
            print(f"❌ Contraseña actual incorrecta para usuario: {user_id}")
            
            if error_message == "INVALID_PASSWORD":
                detail = "La contraseña actual es incorrecta"
            elif error_message == "TOO_MANY_ATTEMPTS_TRY_LATER":
                detail = "Demasiados intentos fallidos. Intenta más tarde"
            else:
                detail = "No se pudo verificar la contraseña actual"
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=detail
            )
        
        print(f"✅ Contraseña actual verificada correctamente")
        
        # PASO 2: Actualizar contraseña en Firebase Auth
        try:
            auth.update_user(
                user_id,
                password=request.new_password
            )
            print(f"✅ Contraseña actualizada en Firebase Auth para usuario: {user_id}")
        except Exception as e:
            print(f"❌ Error al actualizar contraseña en Firebase Auth: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al actualizar contraseña: {str(e)}"
            )
        
        # PASO 3: Registrar cambio en Firestore (opcional, para auditoría)
        db = firebase_service.get_db()
        try:
            db.collection('users').document(user_id).update({
                'password_changed_at': datetime.utcnow()
            })
            print(f"✅ Timestamp de cambio de contraseña registrado en Firestore")
        except Exception as e:
            # No fallar si esto falla
            print(f"⚠️ No se pudo registrar timestamp en Firestore: {str(e)}")
        
        print(f"🎉 Cambio de contraseña completado exitosamente para usuario: {user_id}")
        
        return ChangePasswordResponse(
            message="Contraseña actualizada exitosamente",
            user_id=user_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error en cambio de contraseña: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al cambiar contraseña: {str(e)}"
        )
