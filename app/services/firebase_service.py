import firebase_admin
from firebase_admin import credentials, firestore, auth
from app.config import settings
import os
import json

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
                # Verificar si existe FIREBASE_CREDENTIALS_JSON (Render/Producción)
                firebase_creds_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
                
                if firebase_creds_json:
                    # Usar credenciales desde variable de entorno
                    cred_dict = json.loads(firebase_creds_json)
                    cred = credentials.Certificate(cred_dict)
                    print("✅ Usando credenciales desde variable de entorno (Producción)")
                else:
                    # Usar archivo local (desarrollo)
                    cred_path = settings.firebase_credentials_path
                    if not os.path.exists(cred_path):
                        raise FileNotFoundError(f"No se encontró el archivo de credenciales: {cred_path}")
                    cred = credentials.Certificate(cred_path)
                    print("✅ Usando credenciales desde archivo local (Desarrollo)")
                
                # Inicializar Firebase Admin SDK
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