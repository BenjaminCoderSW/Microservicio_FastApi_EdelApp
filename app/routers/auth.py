from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.user import RegisterRequest, LoginRequest, LoginResponse
from app.services.firebase_service import firebase_service
from app.utils.auth_utils import create_access_token, verify_token, invalidate_token
from firebase_admin import auth
from datetime import datetime
import requests
from app.config import settings
from typing import Optional

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()

@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
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
        # Verificar si el email ya existe
        try:
            existing_user = auth.get_user_by_email(request.email)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )
        except auth.UserNotFoundError:
            pass  # Email no existe, podemos continuar
        
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar usuario: {str(e)}"
        )

@router.post("/login", response_model=LoginResponse)
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al iniciar sesión: {str(e)}"
        )

@router.post("/logout")
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
        
        return {
            "message": "Sesión cerrada exitosamente",
            "user_id": payload.get('uid')
        }
        
    except Exception as e:
        print(f"❌ Error en logout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al cerrar sesión: {str(e)}"
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