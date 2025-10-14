import firebase_admin
from firebase_admin import credentials, firestore, auth
from app.config import settings
import os

class FirebaseService:
    """Servicio singleton para manejar conexión con Firebase"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not FirebaseService._initialized:
            try:
                # Verificar que el archivo de credenciales existe
                cred_path = settings.firebase_credentials_path
                if not os.path.exists(cred_path):
                    raise FileNotFoundError(f"No se encontró el archivo de credenciales: {cred_path}")
                
                # Inicializar Firebase Admin SDK
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                
                # Obtener instancia de Firestore
                self.db = firestore.client()
                
                FirebaseService._initialized = True
                print("✅ Firebase inicializado correctamente")
                
            except Exception as e:
                print(f"❌ Error al inicializar Firebase: {str(e)}")
                raise
    
    def get_db(self):
        """Retorna instancia de Firestore"""
        return self.db
    
    def get_auth(self):
        """Retorna módulo de autenticación de Firebase"""
        return auth

# Crear instancia global
firebase_service = FirebaseService()