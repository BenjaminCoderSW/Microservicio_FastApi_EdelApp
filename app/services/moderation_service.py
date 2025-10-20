import requests
from typing import Dict, List, Optional
from app.models.post import ModerationResult
from app.config import settings

class ModerationService:
    """Servicio para moderar contenido usando múltiples APIs"""
    
    def __init__(self):
        self.moderatecontent_enabled = hasattr(settings, 'moderatecontent_api_key') and settings.moderatecontent_api_key
        self.openai_enabled = hasattr(settings, 'openai_api_key') and settings.openai_api_key
        self.sightengine_enabled = (
            hasattr(settings, 'sightengine_api_user') and settings.sightengine_api_user and
            hasattr(settings, 'sightengine_api_secret') and settings.sightengine_api_secret
        )
        # PurgoMalum no requiere API key
        self.purgomalum_enabled = True
    
    def moderate_content(self, text: str) -> ModerationResult:
        """
        Moderar contenido de texto usando múltiples servicios
        
        Args:
            text: Texto a moderar
            
        Returns:
            ModerationResult con el resultado de la moderación
        """
        flagged_by = []
        reason = None
        
        # 1. PurgoMalum - Detección de profanidad (gratuito, sin API key)
        if self.purgomalum_enabled:
            if not self._check_purgomalum(text):
                flagged_by.append("PurgoMalum")
                reason = "Contenido contiene lenguaje inapropiado o profanidad"
        
        # 2. ModerateContent API (si está configurada)
        if self.moderatecontent_enabled:
            if not self._check_moderatecontent(text):
                flagged_by.append("ModerateContent")
                if not reason:
                    reason = "Contenido inapropiado detectado por ModerateContent"
        
        # 3. OpenAI Moderation API (si está configurada)
        if self.openai_enabled:
            if not self._check_openai_moderation(text):
                flagged_by.append("OpenAI")
                if not reason:
                    reason = "Contenido inapropiado detectado por OpenAI"
        
        # 4. Sightengine Text Moderation (si está configurada)
        if self.sightengine_enabled:
            if not self._check_sightengine_text(text):
                flagged_by.append("Sightengine")
                if not reason:
                    reason = "Contenido inapropiado detectado por Sightengine"
        
        # Si algún servicio lo marcó, el contenido NO es seguro
        is_safe = len(flagged_by) == 0
        
        return ModerationResult(
            is_safe=is_safe,
            reason=reason,
            flagged_by=flagged_by
        )
    
    def moderate_image(self, image_url: str) -> ModerationResult:
        """
        Moderar imagen usando Sightengine API
        
        Args:
            image_url: URL de la imagen a moderar
            
        Returns:
            ModerationResult con el resultado de la moderación
        """
        flagged_by = []
        reason = None
        
        if self.sightengine_enabled:
            result = self._check_sightengine_image(image_url)
            if not result['is_safe']:
                flagged_by.append("Sightengine")
                reason = result['reason']
        else:
            # Si no está configurado Sightengine, la imagen pasa por defecto
            print("⚠️ Sightengine no configurado - imagen no moderada")
            return ModerationResult(
                is_safe=True,
                reason="Moderación de imágenes no disponible",
                flagged_by=[]
            )
        
        is_safe = len(flagged_by) == 0
        
        return ModerationResult(
            is_safe=is_safe,
            reason=reason,
            flagged_by=flagged_by
        )
    
    def _check_purgomalum(self, text: str) -> bool:
        """
        Verificar contenido con PurgoMalum API
        
        Returns:
            True si el contenido es seguro, False si contiene profanidad
        """
        try:
            url = "https://www.purgomalum.com/service/containsprofanity"
            params = {"text": text}
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                # La API retorna "true" o "false" como string
                contains_profanity = response.text.strip().lower() == "true"
                is_safe = not contains_profanity
                
                print(f"✅ PurgoMalum check: {'SAFE' if is_safe else 'FLAGGED'}")
                return is_safe
            else:
                print(f"⚠️ PurgoMalum error: {response.status_code}")
                return True  # Si falla, no bloqueamos el contenido
                
        except Exception as e:
            print(f"⚠️ Error en PurgoMalum: {str(e)}")
            return True  # Si falla, no bloqueamos el contenido
    
    def _check_moderatecontent(self, text: str) -> bool:
        """
        Verificar contenido con ModerateContent API
        
        Returns:
            True si el contenido es seguro, False si es inapropiado
        """
        if not self.moderatecontent_enabled:
            return True
        
        try:
            url = "https://moderatecontent.com/api/v1"
            headers = {"API-KEY": settings.moderatecontent_api_key}
            data = {"text": text}
            
            response = requests.post(url, headers=headers, json=data, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                is_safe = result.get("rating", "safe") == "safe"
                
                print(f"✅ ModerateContent check: {'SAFE' if is_safe else 'FLAGGED'}")
                return is_safe
            else:
                print(f"⚠️ ModerateContent error: {response.status_code}")
                return True
                
        except Exception as e:
            print(f"⚠️ Error en ModerateContent: {str(e)}")
            return True
    
    def _check_openai_moderation(self, text: str) -> bool:
        """
        Verificar contenido con OpenAI Moderation API
        
        Returns:
            True si el contenido es seguro, False si es inapropiado
        """
        if not self.openai_enabled:
            return True
        
        try:
            url = "https://api.openai.com/v1/moderations"
            headers = {
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json"
            }
            data = {"input": text}
            
            response = requests.post(url, headers=headers, json=data, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                # OpenAI retorna un array de resultados
                if result.get("results") and len(result["results"]) > 0:
                    flagged = result["results"][0].get("flagged", False)
                    is_safe = not flagged
                    
                    print(f"✅ OpenAI Moderation check: {'SAFE' if is_safe else 'FLAGGED'}")
                    return is_safe
                return True
            else:
                print(f"⚠️ OpenAI Moderation error: {response.status_code}")
                return True
                
        except Exception as e:
            print(f"⚠️ Error en OpenAI Moderation: {str(e)}")
            return True
    
    def _check_sightengine_text(self, text: str) -> bool:
        """
        Verificar texto con Sightengine API
        
        Returns:
            True si el contenido es seguro, False si es inapropiado
        """
        if not self.sightengine_enabled:
            return True
        
        try:
            url = "https://api.sightengine.com/1.0/text/check.json"
            params = {
                'text': text,
                'mode': 'standard',
                'lang': 'es,en',  # Español e Inglés
                'categories': 'profanity,personal,link',
                'api_user': settings.sightengine_api_user,
                'api_secret': settings.sightengine_api_secret
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                # Verificar profanidad
                profanity = result.get('profanity', {})
                if profanity.get('matches', []):
                    print(f"❌ Sightengine Text: Profanidad detectada")
                    return False
                
                # Verificar información personal
                personal = result.get('personal', {})
                if personal.get('matches', []):
                    print(f"⚠️ Sightengine Text: Información personal detectada")
                    # Esto es warning, no bloquear necesariamente
                
                print(f"✅ Sightengine Text check: SAFE")
                return True
            else:
                print(f"⚠️ Sightengine Text error: {response.status_code}")
                return True
                
        except Exception as e:
            print(f"⚠️ Error en Sightengine Text: {str(e)}")
            return True
    
    def _check_sightengine_image(self, image_url: str) -> Dict:
        """
        Verificar imagen con Sightengine API
        
        Args:
            image_url: URL de la imagen a verificar
            
        Returns:
            Dict con is_safe (bool) y reason (str)
        """
        if not self.sightengine_enabled:
            return {'is_safe': True, 'reason': None}
        
        try:
            url = "https://api.sightengine.com/1.0/check.json"
            params = {
                'url': image_url,
                'models': 'nudity-2.0,wad,offensive,gore,text-content',
                'api_user': settings.sightengine_api_user,
                'api_secret': settings.sightengine_api_secret
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                
                # 1. Verificar desnudez
                nudity = result.get('nudity', {})
                if nudity.get('sexual_activity', 0) > 0.5 or nudity.get('sexual_display', 0) > 0.5:
                    print(f"❌ Sightengine Image: Contenido sexual detectado")
                    return {
                        'is_safe': False,
                        'reason': 'Imagen contiene contenido sexual o desnudez inapropiada'
                    }
                
                # 2. Verificar armas, alcohol, drogas
                wad = result.get('weapon', 0)
                if wad > 0.7:
                    print(f"❌ Sightengine Image: Armas detectadas")
                    return {
                        'is_safe': False,
                        'reason': 'Imagen contiene armas'
                    }
                
                # 3. Verificar contenido ofensivo
                offensive = result.get('offensive', {})
                if offensive.get('prob', 0) > 0.6:
                    print(f"❌ Sightengine Image: Contenido ofensivo detectado")
                    return {
                        'is_safe': False,
                        'reason': 'Imagen contiene contenido ofensivo'
                    }
                
                # 4. Verificar gore/violencia
                gore = result.get('gore', {})
                if gore.get('prob', 0) > 0.5:
                    print(f"❌ Sightengine Image: Contenido violento/gore detectado")
                    return {
                        'is_safe': False,
                        'reason': 'Imagen contiene contenido violento o gore'
                    }
                
                print(f"✅ Sightengine Image check: SAFE")
                return {'is_safe': True, 'reason': None}
            else:
                print(f"⚠️ Sightengine Image error: {response.status_code}")
                return {'is_safe': True, 'reason': None}  # Si falla, no bloqueamos
                
        except Exception as e:
            print(f"⚠️ Error en Sightengine Image: {str(e)}")
            return {'is_safe': True, 'reason': None}  # Si falla, no bloqueamos

# Instancia global del servicio
moderation_service = ModerationService()