"""
Middleware para FastAPI que integra el sistema de logging SOTA

Este middleware proporciona:
- Tracking automático de requests con correlation IDs
- Logging de requests/responses
- Métricas de rendimiento
- Manejo de errores con logging detallado
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .config import (
    get_logger, 
    get_loguru_logger,
    CorrelationContext,
    correlation_id,
    user_id,
    session_id
)

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware para logging automático de requests HTTP
    """
    
    def __init__(self, app: ASGIApp, exclude_paths: list = None):
        super().__init__(app)
        self.logger = get_logger(__name__)
        self.loguru_logger = get_loguru_logger()
        self.exclude_paths = exclude_paths or ['/health', '/metrics', '/docs', '/openapi.json']
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Saltar paths excluidos
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Generar correlation ID
        request_correlation_id = str(uuid.uuid4())
        
        # Extraer información del usuario si está disponible
        user_id_value = self._extract_user_id(request)
        session_id_value = self._extract_session_id(request)
        
        # Configurar contexto de correlación
        with CorrelationContext(
            correlation_id_value=request_correlation_id,
            user_id_value=user_id_value,
            session_id_value=session_id_value
        ):
            start_time = time.time()
            
            # Log del request entrante
            await self._log_request(request, request_correlation_id)
            
            try:
                # Procesar request
                response = await call_next(request)
                
                # Calcular tiempo de procesamiento
                process_time = time.time() - start_time
                
                # Agregar headers de correlación
                response.headers["X-Correlation-ID"] = request_correlation_id
                response.headers["X-Process-Time"] = str(process_time)
                
                # Log del response
                await self._log_response(request, response, process_time)
                
                return response
                
            except Exception as e:
                # Log del error
                process_time = time.time() - start_time
                await self._log_error(request, e, process_time)
                
                # Retornar respuesta de error estructurada
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "Internal Server Error",
                        "correlation_id": request_correlation_id,
                        "message": "An unexpected error occurred"
                    },
                    headers={
                        "X-Correlation-ID": request_correlation_id,
                        "X-Process-Time": str(process_time)
                    }
                )
    
    def _extract_user_id(self, request: Request) -> str:
        """Extraer user ID del request (headers, JWT, etc.)"""
        # Buscar en headers
        user_id_header = request.headers.get('X-User-ID')
        if user_id_header:
            return user_id_header
        
        # Buscar en query params
        user_id_param = request.query_params.get('user_id')
        if user_id_param:
            return user_id_param
        
        # TODO: Extraer de JWT token cuando esté implementado
        # auth_header = request.headers.get('Authorization')
        # if auth_header and auth_header.startswith('Bearer '):
        #     token = auth_header.split(' ')[1]
        #     # Decodificar JWT y extraer user_id
        
        return None
    
    def _extract_session_id(self, request: Request) -> str:
        """Extraer session ID del request"""
        # Buscar en headers
        session_id_header = request.headers.get('X-Session-ID')
        if session_id_header:
            return session_id_header
        
        # Buscar en cookies
        session_cookie = request.cookies.get('session_id')
        if session_cookie:
            return session_cookie
        
        return None
    
    async def _log_request(self, request: Request, correlation_id: str):
        """Log del request entrante"""
        # Obtener información del request
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        # Obtener body si existe (para POST/PUT)
        body = None
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                body = await request.body()
                # Limitar tamaño del body en logs
                if len(body) > 1000:
                    body = body[:1000] + b'...[truncated]'
                body = body.decode('utf-8', errors='ignore')
            except Exception:
                body = '[Unable to decode body]'
        
        self.logger.info(
            "HTTP Request received",
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            query_params=dict(request.query_params),
            headers=dict(request.headers),
            client_ip=client_ip,
            user_agent=user_agent,
            body=body,
            correlation_id=correlation_id
        )
    
    async def _log_response(self, request: Request, response: Response, process_time: float):
        """Log del response saliente"""
        self.logger.info(
            "HTTP Response sent",
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            status_code=response.status_code,
            process_time=f"{process_time:.4f}s",
            response_size=response.headers.get('content-length', 'unknown')
        )
        
        # Log de métricas de rendimiento
        if process_time > 1.0:  # Requests lentos
            self.logger.warning(
                "Slow request detected",
                method=request.method,
                path=request.url.path,
                process_time=f"{process_time:.4f}s",
                threshold="1.0s"
            )
    
    async def _log_error(self, request: Request, error: Exception, process_time: float):
        """Log de errores"""
        self.logger.error(
            "HTTP Request failed",
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            error=str(error),
            error_type=type(error).__name__,
            process_time=f"{process_time:.4f}s"
        )
        
        # Log detallado con loguru para debugging
        self.loguru_logger.exception(
            f"Request failed: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "error_type": type(error).__name__,
                "process_time": process_time
            }
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """Obtener IP del cliente considerando proxies"""
        # Buscar en headers de proxy
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        # IP directa
        if request.client:
            return request.client.host
        
        return 'unknown'

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware para recolección de métricas básicas
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = get_logger(__name__)
        self.request_count = 0
        self.error_count = 0
        self.total_process_time = 0.0
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        self.request_count += 1
        
        try:
            response = await call_next(request)
            
            # Calcular métricas
            process_time = time.time() - start_time
            self.total_process_time += process_time
            
            # Log de métricas cada 100 requests
            if self.request_count % 100 == 0:
                avg_response_time = self.total_process_time / self.request_count
                error_rate = (self.error_count / self.request_count) * 100
                
                self.logger.info(
                    "Application metrics",
                    total_requests=self.request_count,
                    total_errors=self.error_count,
                    error_rate=f"{error_rate:.2f}%",
                    avg_response_time=f"{avg_response_time:.4f}s"
                )
            
            return response
            
        except Exception as e:
            self.error_count += 1
            raise e 