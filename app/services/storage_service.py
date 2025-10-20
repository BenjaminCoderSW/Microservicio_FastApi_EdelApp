from firebase_admin import storage
from datetime import timedelta
import uuid
from typing import Optional
import base64
import mimetypes

class StorageService:
    """Servicio para manejar uploads a Firebase Storage"""
    
    def __init__(self):
        # Obtener referencia al bucket de Storage
        self.bucket = storage.bucket()
        
        # Tipos de imagen permitidos
        self.allowed_types = [
            'image/jpeg',
            'image/jpg',
            'image/png',
            'image/gif',
            'image/webp'
        ]
        
        # Tamaño máximo: 5MB
        self.max_size_bytes = 5 * 1024 * 1024
    
    def upload_post_image(self, image_data: str, user_id: str) -> str:
        """
        Subir imagen de post a Firebase Storage
        
        Args:
            image_data: Datos de la imagen en base64 o bytes
            user_id: ID del usuario que sube la imagen
            
        Returns:
            URL pública de la imagen subida
            
        Raises:
            ValueError: Si la imagen no es válida
        """
        try:
            # Generar nombre único para la imagen
            image_id = str(uuid.uuid4())
            file_path = f"posts/{user_id}/{image_id}.jpg"
            
            # Crear blob en el bucket
            blob = self.bucket.blob(file_path)
            
            # Decodificar base64 si es necesario
            if isinstance(image_data, str):
                if image_data.startswith('data:image'):
                    # Formato: data:image/jpeg;base64,/9j/4AAQ...
                    image_data = image_data.split(',')[1]
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data
            
            # Validar tamaño
            if len(image_bytes) > self.max_size_bytes:
                raise ValueError(f"Imagen demasiado grande. Máximo: 5MB")
            
            # Subir imagen
            blob.upload_from_string(
                image_bytes,
                content_type='image/jpeg'
            )
            
            # Hacer la imagen pública
            blob.make_public()
            
            # Obtener URL pública
            public_url = blob.public_url
            
            print(f"✅ Imagen subida: {file_path}")
            return public_url
            
        except Exception as e:
            print(f"❌ Error al subir imagen: {str(e)}")
            raise ValueError(f"Error al subir imagen: {str(e)}")
    
    def upload_profile_image(self, image_data: str, user_id: str) -> str:
        """
        Subir imagen de perfil a Firebase Storage
        
        Args:
            image_data: Datos de la imagen en base64 o bytes
            user_id: ID del usuario
            
        Returns:
            URL pública de la imagen subida
        """
        try:
            file_path = f"profiles/{user_id}/avatar.jpg"
            
            blob = self.bucket.blob(file_path)
            
            # Decodificar base64 si es necesario
            if isinstance(image_data, str):
                if image_data.startswith('data:image'):
                    image_data = image_data.split(',')[1]
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data
            
            # Validar tamaño
            if len(image_bytes) > self.max_size_bytes:
                raise ValueError(f"Imagen demasiado grande. Máximo: 5MB")
            
            # Subir imagen
            blob.upload_from_string(
                image_bytes,
                content_type='image/jpeg'
            )
            
            # Hacer la imagen pública
            blob.make_public()
            
            # Obtener URL pública
            public_url = blob.public_url
            
            print(f"✅ Imagen de perfil subida: {file_path}")
            return public_url
            
        except Exception as e:
            print(f"❌ Error al subir imagen de perfil: {str(e)}")
            raise ValueError(f"Error al subir imagen de perfil: {str(e)}")
    
    def delete_image(self, image_url: str) -> bool:
        """
        Eliminar imagen de Firebase Storage
        
        Args:
            image_url: URL de la imagen a eliminar
            
        Returns:
            True si se eliminó exitosamente
        """
        try:
            # Extraer path del blob desde la URL
            # URL format: https://storage.googleapis.com/bucket-name/path/to/file
            path = image_url.split(self.bucket.name + '/')[-1]
            
            blob = self.bucket.blob(path)
            blob.delete()
            
            print(f"✅ Imagen eliminada: {path}")
            return True
            
        except Exception as e:
            print(f"⚠️ Error al eliminar imagen: {str(e)}")
            return False

# Instancia global del servicio
storage_service = StorageService()