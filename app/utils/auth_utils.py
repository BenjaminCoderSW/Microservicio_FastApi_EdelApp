from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, status, Header
from typing import Optional
from app.config import settings

# Blacklist de tokens (en producción usar Redis)
token_blacklist = set()

def create_access_token(data: dict) -> str:
    """
    Crear token JWT SIN EXPIRACIÓN
    
    Args:
        data: Datos a incluir en el token
        
    Returns:
        Token JWT como string
    """
    to_encode = data.copy()
    # MEJOR YA NO SE AGREGA LA FECHA DE EXPIRACION  DE TOKEN PARA PRUEBAS MAS FACILES
    # expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)
    #to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.jwt_secret_key, 
        algorithm=settings.jwt_algorithm
    )
    
    return encoded_jwt

def verify_token(token: str) -> dict:
    """
    Verificar y decodificar token JWT
    
    Args:
        token: Token JWT a verificar
        
    Returns:
        Payload del token decodificado
        
    Raises:
        HTTPException: Si el token es inválido
    """
    # Verificar si está en blacklist
    if token in token_blacklist:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )
    
    try:
        # MODIFICADO: Se desactiva la verificación de expiración
        payload = jwt.decode(
            token, 
            settings.jwt_secret_key, 
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False}  # AGREGADO: Desactiva verificación de expiración de token
        )
        return payload
    # REMOVIDO YA QUE SE QUISO DESACTIVAR LA EXPIRACION DEL TOKEN
    # except jwt.ExpiredSignatureError:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Token expirado"
    #     )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )

async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    Dependency para obtener usuario actual desde JWT
    
    Args:
        authorization: Header de autorización con formato "Bearer {token}"
        
    Returns:
        Payload del token con información del usuario
        
    Raises:
        HTTPException: Si no hay token o es inválido
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no proporcionado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if not authorization.startswith('Bearer '):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de token inválido. Use: Bearer {token}",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = authorization.split(' ')[1]
    return verify_token(token)

def invalidate_token(token: str) -> None:
    """
    Agregar token a blacklist
    
    Args:
        token: Token JWT a invalidar
    """
    token_blacklist.add(token)