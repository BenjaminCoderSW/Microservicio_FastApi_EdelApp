from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.interactions import (
    CreateReportRequest, 
    ReportResponse, 
    ReportListResponse,
    UpdateReportStatusRequest
)
from app.services.firebase_service import firebase_service
from app.utils.auth_utils import verify_token
from datetime import datetime
import uuid
from typing import Optional

router = APIRouter(prefix="/reports", tags=["Reports"])
security = HTTPBearer()

# Razones de reporte válidas
VALID_REASONS = [
    "spam",           # Contenido de spam
    "harassment",     # Acoso o bullying
    "violence",       # Violencia o contenido gráfico
    "hate_speech",    # Discurso de odio
    "misinformation", # Información falsa
    "other"           # Otra razón
]

# Estados válidos para reportes
VALID_STATUSES = ["pending", "reviewed", "resolved"]

@router.post("/posts/{post_id}", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    post_id: str,
    request: CreateReportRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Reportar un post
    
    - Crea documento en colección 'reports'
    - Valida que el post existe
    - Previene reportes duplicados del mismo usuario al mismo post
    - Estado inicial: "pending"
    
    **Header requerido:**
    - Authorization: Bearer {token}
    
    **Body:**
    - reason: Razón del reporte (spam, harassment, violence, hate_speech, misinformation, other)
    - description: Descripción adicional opcional
    
    **Respuesta:**
    - Datos completos del reporte creado
    """
    try:
        # Verificar token
        token = credentials.credentials
        current_user = verify_token(token)
        user_id = current_user['uid']
        
        # Validar razón
        if request.reason not in VALID_REASONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Razón inválida. Debe ser una de: {', '.join(VALID_REASONS)}"
            )
        
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
        
        # 2. VERIFICAR QUE EL USUARIO NO HAYA REPORTADO YA ESTE POST
        existing_report = db.collection('reports')\
            .where('post_id', '==', post_id)\
            .where('reported_by', '==', user_id)\
            .limit(1)\
            .get()
        
        if len(list(existing_report)) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya has reportado este post previamente"
            )
        
        # 3. CREAR REPORTE
        report_id = str(uuid.uuid4())
        report_data = {
            'report_id': report_id,
            'post_id': post_id,
            'reported_by': user_id,
            'reason': request.reason,
            'description': request.description,
            'status': 'pending',
            'created_at': datetime.utcnow(),
            'reviewed_at': None,
            'reviewed_by': None
        }
        
        db.collection('reports').document(report_id).set(report_data)
        
        print(f"✅ Reporte creado: {report_id} para post {post_id}")
        
        return ReportResponse(
            report_id=report_id,
            post_id=post_id,
            reported_by=user_id,
            reason=request.reason,
            description=request.description,
            status='pending',
            created_at=report_data['created_at'],
            reviewed_at=None,
            reviewed_by=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al crear reporte: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear reporte: {str(e)}"
        )

@router.get("/", response_model=ReportListResponse)
async def get_reports(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    status_filter: Optional[str] = Query(None, description="Filtrar por estado (pending, reviewed, resolved)")
):
    """
    Obtener todos los reportes (SOLO ADMIN)
    
    - Requiere usuario con is_admin = true
    - Retorna reportes ordenados por fecha (más recientes primero)
    - Permite filtrar por estado
    - Incluye contador de reportes pendientes
    
    **Header requerido:**
    - Authorization: Bearer {token} (con permisos de admin)
    
    **Query params:**
    - status: Filtrar por estado (opcional)
    
    **Respuesta:**
    - Lista de reportes
    - Total de reportes
    - Contador de reportes pendientes
    """
    try:
        # Verificar token
        token = credentials.credentials
        current_user = verify_token(token)
        user_id = current_user['uid']
        
        db = firebase_service.get_db()
        
        # VERIFICAR QUE EL USUARIO ES ADMIN
        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        user_data = user_doc.to_dict()
        if not user_data.get('is_admin', False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos de administrador"
            )
        
        # CONSTRUIR QUERY
        query = db.collection('reports')
        
        # Aplicar filtro de estado si se proporcionó
        if status_filter:
            if status_filter not in VALID_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Estado inválido. Debe ser uno de: {', '.join(VALID_STATUSES)}"
                )
            query = query.where('status', '==', status_filter)
        
        # Ordenar por fecha descendente
        query = query.order_by('created_at', direction='DESCENDING')
        
        # OBTENER REPORTES
        reports_docs = list(query.stream())
        
        # Convertir a ReportResponse
        reports_list = []
        for report_doc in reports_docs:
            report_data = report_doc.to_dict()
            reports_list.append(ReportResponse(
                report_id=report_data['report_id'],
                post_id=report_data['post_id'],
                reported_by=report_data['reported_by'],
                reason=report_data['reason'],
                description=report_data.get('description'),
                status=report_data['status'],
                created_at=report_data['created_at'],
                reviewed_at=report_data.get('reviewed_at'),
                reviewed_by=report_data.get('reviewed_by')
            ))
        
        # CONTAR REPORTES PENDIENTES
        pending_query = db.collection('reports').where('status', '==', 'pending').get()
        pending_count = len(list(pending_query))
        
        print(f"✅ Reportes obtenidos: total={len(reports_list)}, pendientes={pending_count}")
        
        return ReportListResponse(
            reports=reports_list,
            total=len(reports_list),
            pending_count=pending_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al obtener reportes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener reportes: {str(e)}"
        )

@router.put("/{report_id}/status")
async def update_report_status(
    report_id: str,
    request: UpdateReportStatusRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Actualizar estado de un reporte (SOLO ADMIN)
    
    - Requiere usuario con is_admin = true
    - Permite cambiar estado a: reviewed, resolved
    - No permite cambiar de vuelta a pending
    - Registra quién y cuándo revisó el reporte
    
    **Header requerido:**
    - Authorization: Bearer {token} (con permisos de admin)
    
    **Body:**
    - status: Nuevo estado (reviewed, resolved)
    
    **Respuesta:**
    - Mensaje de éxito
    """
    try:
        # Verificar token
        token = credentials.credentials
        current_user = verify_token(token)
        user_id = current_user['uid']
        
        # Validar nuevo estado
        if request.status not in ['reviewed', 'resolved']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Estado inválido. Debe ser 'reviewed' o 'resolved'"
            )
        
        db = firebase_service.get_db()
        
        # VERIFICAR QUE EL USUARIO ES ADMIN
        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        user_data = user_doc.to_dict()
        if not user_data.get('is_admin', False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos de administrador"
            )
        
        # VERIFICAR QUE EL REPORTE EXISTE
        report_doc = db.collection('reports').document(report_id).get()
        if not report_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reporte no encontrado"
            )
        
        # ACTUALIZAR ESTADO
        update_data = {
            'status': request.status,
            'reviewed_at': datetime.utcnow(),
            'reviewed_by': user_id
        }
        
        db.collection('reports').document(report_id).update(update_data)
        
        print(f"✅ Estado de reporte actualizado: {report_id} -> {request.status}")
        
        return {
            "message": f"Estado actualizado a '{request.status}' exitosamente",
            "report_id": report_id,
            "new_status": request.status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al actualizar estado de reporte: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar estado de reporte: {str(e)}"
        )

@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Obtener reporte específico por ID (SOLO ADMIN)
    
    - Requiere usuario con is_admin = true
    - Retorna detalles completos del reporte
    
    **Header requerido:**
    - Authorization: Bearer {token} (con permisos de admin)
    
    **Respuesta:**
    - Datos completos del reporte
    """
    try:
        # Verificar token
        token = credentials.credentials
        current_user = verify_token(token)
        user_id = current_user['uid']
        
        db = firebase_service.get_db()
        
        # VERIFICAR QUE EL USUARIO ES ADMIN
        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        user_data = user_doc.to_dict()
        if not user_data.get('is_admin', False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos de administrador"
            )
        
        # OBTENER REPORTE
        report_doc = db.collection('reports').document(report_id).get()
        if not report_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reporte no encontrado"
            )
        
        report_data = report_doc.to_dict()
        
        print(f"✅ Reporte obtenido: {report_id}")
        
        return ReportResponse(
            report_id=report_data['report_id'],
            post_id=report_data['post_id'],
            reported_by=report_data['reported_by'],
            reason=report_data['reason'],
            description=report_data.get('description'),
            status=report_data['status'],
            created_at=report_data['created_at'],
            reviewed_at=report_data.get('reviewed_at'),
            reviewed_by=report_data.get('reviewed_by')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al obtener reporte: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener reporte: {str(e)}"
        )