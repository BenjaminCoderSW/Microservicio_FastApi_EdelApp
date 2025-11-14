from firebase_admin import storage
from datetime import timedelta
import uuid
from typing import Optional
import base64
import mimetypes
from PIL import Image
import io

class StorageService:
    """Servicio para manejar uploads a Firebase Storage con compresión automática"""
    
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
        
        # Tamaño máximo ANTES de compresión: 10MB (más permisivo)
        self.max_size_bytes = 10 * 1024 * 1024
        
        # CONFIGURACIÓN DE COMPRESIÓN
        self.max_width = 1920  # Ancho máximo en pixels
        self.max_height = 1920  # Alto máximo en pixels
        self.jpeg_quality = 85  # Calidad JPEG (0-100, 85 es buen balance)
        self.target_size_kb = 500  # Tamaño objetivo después de compresión (500KB)
    
    def compress_image(self, image_bytes: bytes) -> bytes:
        """
        Comprimir imagen para optimizar uso de datos
        
        Args:
            image_bytes: Bytes de la imagen original
            
        Returns:
            Bytes de la imagen comprimida
        """
        try:
            # Abrir imagen con Pillow
            img = Image.open(io.BytesIO(image_bytes))
            
            # Convertir RGBA a RGB si es necesario (para JPEG)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Obtener dimensiones originales
            original_width, original_height = img.size
            original_size_kb = len(image_bytes) / 1024
            
            print(f"📷 Imagen original: {original_width}x{original_height}, {original_size_kb:.1f}KB")
            
            # PASO 1: Redimensionar si es necesario
            if original_width > self.max_width or original_height > self.max_height:
                # Mantener aspect ratio
                img.thumbnail((self.max_width, self.max_height), Image.Resampling.LANCZOS)
                new_width, new_height = img.size
                print(f"📏 Redimensionada a: {new_width}x{new_height}")
            
            # PASO 2: Comprimir con calidad adaptativa
            quality = self.jpeg_quality
            output = io.BytesIO()
            
            # Intentar comprimir hasta alcanzar el tamaño objetivo
            for attempt in range(5):  # Máximo 5 intentos
                output.seek(0)
                output.truncate()
                
                img.save(output, format='JPEG', quality=quality, optimize=True)
                compressed_size_kb = output.tell() / 1024
                
                # Si alcanzamos el tamaño objetivo, terminar
                if compressed_size_kb <= self.target_size_kb or quality <= 60:
                    break
                
                # Reducir calidad para siguiente intento
                quality -= 10
                print(f"🔄 Intento {attempt + 1}: {compressed_size_kb:.1f}KB con calidad {quality + 10}%, ajustando...")
            
            compressed_bytes = output.getvalue()
            final_size_kb = len(compressed_bytes) / 1024
            compression_ratio = (1 - final_size_kb / original_size_kb) * 100
            
            print(f"✅ Compresión exitosa: {original_size_kb:.1f}KB → {final_size_kb:.1f}KB (ahorro: {compression_ratio:.1f}%)")
            print(f"📊 Calidad final: {quality}")
            
            return compressed_bytes
            
        except Exception as e:
            print(f"⚠️ Error al comprimir imagen, usando original: {str(e)}")
            # Si falla la compresión, retornar imagen original
            return image_bytes
    
    def upload_post_image(self, image_data: str, user_id: str) -> str:
        """
        Subir imagen de post a Firebase Storage CON COMPRESIÓN AUTOMÁTICA
        
        Args:
            image_data: Datos de la imagen en base64 o bytes
            user_id: ID del usuario que sube la imagen
            
        Returns:
            URL pública de la imagen subida (comprimida)
            
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
            
            # Validar tamaño ANTES de compresión (límite más permisivo)
            if len(image_bytes) > self.max_size_bytes:
                raise ValueError(f"Imagen demasiado grande. Máximo: 10MB")
            
            # 🎯 COMPRIMIR IMAGEN AUTOMÁTICAMENTE
            print(f"🔧 Iniciando compresión de imagen para post...")
            compressed_bytes = self.compress_image(image_bytes)
            
            # Subir imagen COMPRIMIDA
            blob.upload_from_string(
                compressed_bytes,
                content_type='image/jpeg'
            )
            
            # Hacer la imagen pública
            blob.make_public()
            
            # Obtener URL pública
            public_url = blob.public_url
            
            print(f"✅ Imagen comprimida subida: {file_path}")
            return public_url
            
        except Exception as e:
            print(f"❌ Error al subir imagen: {str(e)}")
            raise ValueError(f"Error al subir imagen: {str(e)}")
    
    def upload_profile_image(self, image_data: str, user_id: str) -> str:
        """
        Subir imagen de perfil a Firebase Storage CON COMPRESIÓN
        
        Args:
            image_data: Datos de la imagen en base64 o bytes
            user_id: ID del usuario
            
        Returns:
            URL pública de la imagen subida (comprimida)
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
            
            # Validar tamaño ANTES de compresión
            if len(image_bytes) > self.max_size_bytes:
                raise ValueError(f"Imagen demasiado grande. Máximo: 10MB")
            
            # 🎯 COMPRIMIR IMAGEN DE PERFIL
            print(f"🔧 Iniciando compresión de imagen de perfil...")
            compressed_bytes = self.compress_image(image_bytes)
            
            # Subir imagen COMPRIMIDA
            blob.upload_from_string(
                compressed_bytes,
                content_type='image/jpeg'
            )
            
            # Hacer la imagen pública
            blob.make_public()
            
            # Obtener URL pública
            public_url = blob.public_url
            
            print(f"✅ Imagen de perfil comprimida subida: {file_path}")
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