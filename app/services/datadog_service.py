import requests
import time
from functools import wraps
from app.config import settings

class DatadogService:
    """Servicio para integración con Datadog usando API HTTP v2"""
    
    _initialized = False
    
    # ✅ CONSTRUIR URL DINÁMICA SEGÚN EL SITIO
    @classmethod
    def _get_api_url(cls):
        """Obtener URL correcta del API según el sitio de Datadog"""
        site = settings.datadog_site
        # Extraer región (us5, eu, etc.)
        if "us5" in site:
            return "https://api.us5.datadoghq.com/api/v2/series"
        elif "us3" in site:
            return "https://api.us3.datadoghq.com/api/v2/series"
        elif "ap1" in site:
            return "https://api.ap1.datadoghq.com/api/v2/series"
        elif ".eu" in site or "datadoghq.eu" in site:
            return "https://api.datadoghq.eu/api/v2/series"
        else:
            # Default US1
            return "https://api.datadoghq.com/api/v2/series"
    
    # Tipos de métricas según Datadog API v2
    METRIC_TYPES = {
        "count": 0,
        "rate": 1,
        "gauge": 2,
        "unspecified": 3
    }
    
    @classmethod
    def initialize(cls):
        """Inicializar Datadog"""
        if cls._initialized:
            return
        
        if not settings.datadog_enabled:
            print("⚠️ Datadog deshabilitado en configuración")
            return
        
        if not settings.datadog_api_key:
            print("⚠️ Datadog API key no configurada - Datadog deshabilitado")
            return
        
        try:
            api_url = cls._get_api_url()
            print(f"✅ Datadog inicializado: {settings.datadog_service_name}")
            print(f"🌍 Sitio: {settings.datadog_site}")
            print(f"📍 Enviando a: {api_url}")
            print("ℹ️ Usando API HTTP v2 (sin agent)")
            
            cls._initialized = True
            
        except Exception as e:
            print(f"❌ Error al inicializar Datadog: {str(e)}")
            cls._initialized = False
    
    @staticmethod
    def _send_metric(metric_name: str, value: float, metric_type: int, tags: list = None):
        """
        Enviar métrica usando Datadog API v2
        
        Args:
            metric_name: Nombre completo de la métrica
            value: Valor de la métrica
            metric_type: Tipo (0=count, 1=rate, 2=gauge, 3=unspecified)
            tags: Lista de tags
        """
        if not settings.datadog_enabled or not DatadogService._initialized:
            return
        
        try:
            # ✅ USAR URL CORRECTA SEGÚN EL SITIO
            api_url = DatadogService._get_api_url()
            
            # Timestamp en segundos (epoch)
            timestamp = int(time.time())
            
            # Formatear tags correctamente
            formatted_tags = tags or []
            formatted_tags.extend([
                f"service:{settings.datadog_service_name}",
                f"env:{settings.datadog_env}",
                f"version:{settings.datadog_version}"
            ])
            
            # Payload según API v2
            payload = {
                "series": [
                    {
                        "metric": metric_name,
                        "type": metric_type,
                        "points": [
                            {
                                "timestamp": timestamp,
                                "value": value
                            }
                        ],
                        "tags": formatted_tags
                    }
                ]
            }
            
            # Headers
            headers = {
                "DD-API-KEY": settings.datadog_api_key,
                "Content-Type": "application/json"
            }
            
            # Enviar request
            response = requests.post(
                api_url,  # ✅ USA LA URL CORRECTA
                json=payload,
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 202:
                metric_type_name = {0: "count", 1: "rate", 2: "gauge", 3: "unspecified"}.get(metric_type, "unknown")
                print(f"✅ Métrica enviada a {settings.datadog_site}: {metric_name} = {value} (type: {metric_type_name})")
            else:
                print(f"⚠️ Error al enviar métrica: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
            
        except Exception as e:
            print(f"⚠️ Error al enviar métrica {metric_name}: {str(e)}")
    
    @staticmethod
    def increment_counter(metric_name: str, value: int = 1, tags: list = None):
        """Incrementar contador"""
        metric_full_name = f"edel.{metric_name}"
        DatadogService._send_metric(
            metric_full_name, 
            float(value), 
            DatadogService.METRIC_TYPES["count"],
            tags
        )
    
    @staticmethod
    def gauge(metric_name: str, value: float, tags: list = None):
        """Enviar métrica gauge"""
        metric_full_name = f"edel.{metric_name}"
        DatadogService._send_metric(
            metric_full_name, 
            value, 
            DatadogService.METRIC_TYPES["gauge"],
            tags
        )
    
    @staticmethod
    def histogram(metric_name: str, value: float, tags: list = None):
        """Enviar métrica histogram (usa gauge como fallback)"""
        metric_full_name = f"edel.{metric_name}"
        DatadogService._send_metric(
            metric_full_name, 
            value, 
            DatadogService.METRIC_TYPES["gauge"],
            tags
        )
    
    @staticmethod
    def timing(metric_name: str, value: float, tags: list = None):
        """Enviar métrica de timing (en milisegundos)"""
        metric_full_name = f"edel.{metric_name}"
        # Convertir a segundos (Datadog prefiere segundos para timings)
        value_seconds = value / 1000.0
        DatadogService._send_metric(
            metric_full_name, 
            value_seconds, 
            DatadogService.METRIC_TYPES["gauge"],
            tags
        )

# Decorador para medir tiempo de ejecución
def track_execution_time(metric_name: str):
    """Decorador para trackear tiempo de ejecución"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                DatadogService.timing(metric_name, duration_ms, tags=["status:success"])
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                DatadogService.timing(metric_name, duration_ms, tags=["status:error"])
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                DatadogService.timing(metric_name, duration_ms, tags=["status:success"])
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                DatadogService.timing(metric_name, duration_ms, tags=["status:error"])
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Instancia global
datadog_service = DatadogService()