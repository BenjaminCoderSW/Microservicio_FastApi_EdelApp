from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from app.routers import auth
from app.config import settings
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

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

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(auth.router)

@app.get("/", tags=["Root"])
async def root():
    """Endpoint raíz de la API"""
    return {
        "message": "Edel-SocialApp API",
        "version": settings.api_version,
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "auth-service"
    }

# Event handlers
@app.on_event("startup")
async def startup_event():
    print("🚀 Iniciando Edel-SocialApp API...")
    print(f"📚 Documentación disponible en: http://localhost:8000/docs")

@app.on_event("shutdown")
async def shutdown_event():
    print("👋 Cerrando Edel-SocialApp API...")