from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from app.routers import auth, profile, posts, likes, comments, reports, notifications
from app.config import settings
from dotenv import load_dotenv

# Cargar variables de entorno PRIMERO
load_dotenv()

# ✅ INICIALIZAR DATADOG
DATADOG_ENABLED = False
try:
    from app.services.datadog_service import DatadogService
    DatadogService.initialize()
    DATADOG_ENABLED = DatadogService._initialized
    if DATADOG_ENABLED:
        print("✅ Datadog iniciado correctamente")
    else:
        print("⚠️ Datadog deshabilitado (sin credenciales o configuración)")
except ImportError as e:
    print(f"⚠️ Datadog no disponible (dependencias faltantes): {str(e)}")
except Exception as e:
    print(f"⚠️ Error al inicializar Datadog (servicio continuará sin monitoreo): {str(e)}")

# Configurar esquema de seguridad para Swagger UI
security = HTTPBearer()

# Crear instancia de FastAPI
app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(posts.router)
app.include_router(likes.router)
app.include_router(comments.router)
app.include_router(reports.router)
app.include_router(notifications.router)

@app.get("/", tags=["Root"])
async def root():
    """Endpoint raíz de la API"""
    # Trackear métrica
    if DATADOG_ENABLED:
        try:
            from app.services.datadog_service import DatadogService
            DatadogService.increment_counter("api.root.access", tags=["endpoint:/"])
        except:
            pass
    
    return {
        "message": "Edel-SocialApp API",
        "version": settings.api_version,
        "status": "running",
        "docs": "/docs",
        "monitoring": "Datadog Metrics enabled" if DATADOG_ENABLED else "Monitoring disabled",
        "features": [
            "Authentication (Register/Login/Logout)",
            "User Profiles",
            "Posts with Auto-Moderation",
            "Image Upload to Firebase Storage",
            "Likes & Comments",
            "Reports & Admin Moderation",
            "Push Notifications (FCM HTTP v1)",
            "Datadog Custom Metrics" if DATADOG_ENABLED else "Monitoring: Disabled"
        ]
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    if DATADOG_ENABLED:
        try:
            from app.services.datadog_service import DatadogService
            DatadogService.increment_counter("api.health.check", tags=["endpoint:/health"])
        except:
            pass
    
    return {
        "status": "healthy",
        "service": "edel-socialapp-api",
        "features": {
            "auth": "enabled",
            "profile": "enabled",
            "posts": "enabled",
            "moderation": "enabled",
            "likes": "enabled",
            "comments": "enabled",
            "reports": "enabled",
            "notifications": "enabled",
            "datadog": "enabled" if DATADOG_ENABLED else "disabled"
        }
    }

@app.on_event("startup")
async def startup_event():
    print("🚀 Iniciando Edel-SocialApp API...")
    print(f"📚 Documentación disponible en: http://localhost:8000/docs")
    print("✅ Características habilitadas:")
    print("   - Autenticación con JWT")
    print("   - Perfiles de usuario")
    print("   - Posts con moderación automática")
    print("   - Upload de imágenes a Firebase Storage")
    print("   - Likes y comentarios")
    print("   - Sistema de reportes")
    print("   - Notificaciones Push (FCM HTTP v1)")
    if DATADOG_ENABLED:
        print("   - Datadog Custom Metrics ✅")
    else:
        print("   - Datadog Monitoring ❌ (disabled)")

@app.on_event("shutdown")
async def shutdown_event():
    print("👋 Cerrando Edel-SocialApp API...")