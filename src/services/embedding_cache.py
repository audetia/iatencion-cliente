"""
Servicio de Caché de Embeddings
===============================

Implementación simple de caché en memoria para embeddings de queries frecuentes.
Reduce llamadas a la API de Google Embeddings y mejora el rendimiento.

Principios aplicados:
- KISS: Implementación simple en memoria
- YAGNI: Solo las funcionalidades esenciales
- DRY: Lógica centralizada de caché
- SOLID: Responsabilidad única, fácil de extender
"""

import hashlib
import time
import logging
from typing import Dict, List, Optional, Tuple
from threading import Lock

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """
    Caché simple en memoria para embeddings con TTL.
    
    Características:
    - Thread-safe con locks
    - TTL configurable por entrada
    - Limpieza automática de entradas expiradas
    - Hash MD5 de queries como clave
    - Métricas básicas de hit/miss
    """
    
    def __init__(self, default_ttl_seconds: int = 3600, max_size: int = 1000):
        """
        Inicializa el caché de embeddings.
        
        Args:
            default_ttl_seconds (int): TTL por defecto en segundos (1 hora)
            max_size (int): Tamaño máximo del caché
        """
        self.default_ttl = default_ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, Tuple[List[float], float]] = {}  # {hash: (embedding, expiry_time)}
        self._lock = Lock()
        self._hits = 0
        self._misses = 0
        
        logger.info(f"✅ EmbeddingCache inicializado - TTL: {default_ttl_seconds}s, Max size: {max_size}")
    
    def _generate_key(self, query: str) -> str:
        """
        Genera clave hash para la query.
        
        Args:
            query (str): Texto de la query
            
        Returns:
            str: Hash MD5 de la query
        """
        return hashlib.md5(query.strip().lower().encode('utf-8')).hexdigest()
    
    def _is_expired(self, expiry_time: float) -> bool:
        """
        Verifica si una entrada ha expirado.
        
        Args:
            expiry_time (float): Timestamp de expiración
            
        Returns:
            bool: True si ha expirado
        """
        return time.time() > expiry_time
    
    def _cleanup_expired(self) -> int:
        """
        Limpia entradas expiradas del caché.
        
        Returns:
            int: Número de entradas eliminadas
        """
        current_time = time.time()
        expired_keys = [
            key for key, (_, expiry) in self._cache.items() 
            if current_time > expiry
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"🧹 Limpiadas {len(expired_keys)} entradas expiradas del caché")
        
        return len(expired_keys)
    
    def get(self, query: str) -> Optional[List[float]]:
        """
        Obtiene embedding del caché si existe y no ha expirado.
        
        Args:
            query (str): Texto de la query
            
        Returns:
            List[float] | None: Embedding si existe, None si no
        """
        if not query or not query.strip():
            return None
        
        key = self._generate_key(query)
        
        with self._lock:
            if key in self._cache:
                embedding, expiry_time = self._cache[key]
                
                if not self._is_expired(expiry_time):
                    self._hits += 1
                    logger.debug(f"🎯 Cache HIT para query: {query[:50]}...")
                    return embedding
                else:
                    # Eliminar entrada expirada
                    del self._cache[key]
                    logger.debug(f"⏰ Cache EXPIRED para query: {query[:50]}...")
            
            self._misses += 1
            logger.debug(f"❌ Cache MISS para query: {query[:50]}...")
            return None
    
    def put(self, query: str, embedding: List[float], ttl_seconds: Optional[int] = None) -> bool:
        """
        Almacena embedding en el caché.
        
        Args:
            query (str): Texto de la query
            embedding (List[float]): Embedding a almacenar
            ttl_seconds (int, optional): TTL específico, usa default si None
            
        Returns:
            bool: True si se almacenó correctamente
        """
        if not query or not query.strip() or not embedding:
            return False
        
        # Validar dimensionalidad del embedding
        if len(embedding) != 1536:
            logger.warning(f"⚠️ Embedding con dimensionalidad incorrecta: {len(embedding)}, esperada: 1536")
            return False
        
        key = self._generate_key(query)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expiry_time = time.time() + ttl
        
        with self._lock:
            # Limpiar expirados si el caché está lleno
            if len(self._cache) >= self.max_size:
                cleaned = self._cleanup_expired()
                
                # Si sigue lleno después de limpiar, eliminar el más antiguo
                if len(self._cache) >= self.max_size and cleaned == 0:
                    oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
                    del self._cache[oldest_key]
                    logger.debug(f"🗑️ Eliminada entrada más antigua del caché")
            
            self._cache[key] = (embedding, expiry_time)
            logger.debug(f"💾 Embedding almacenado en caché para query: {query[:50]}...")
            return True
    
    def get_stats(self) -> Dict[str, any]:
        """
        Obtiene estadísticas del caché.
        
        Returns:
            dict: Estadísticas de uso del caché
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / max(total_requests, 1)) * 100
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'total_requests': total_requests,
                'hit_rate_percentage': round(hit_rate, 2),
                'default_ttl_seconds': self.default_ttl
            }
    
    def clear(self) -> int:
        """
        Limpia todo el caché.
        
        Returns:
            int: Número de entradas eliminadas
        """
        with self._lock:
            size = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            logger.info(f"🧹 Caché completamente limpiado - {size} entradas eliminadas")
            return size
    
    def cleanup(self) -> int:
        """
        Limpia solo las entradas expiradas.
        
        Returns:
            int: Número de entradas eliminadas
        """
        with self._lock:
            return self._cleanup_expired()


# Instancia global del caché (singleton simple)
_embedding_cache: Optional[EmbeddingCache] = None


def get_embedding_cache() -> EmbeddingCache:
    """
    Obtiene la instancia global del caché de embeddings.
    
    Returns:
        EmbeddingCache: Instancia del caché
    """
    global _embedding_cache
    if _embedding_cache is None:
        _embedding_cache = EmbeddingCache()
    return _embedding_cache


def clear_embedding_cache() -> int:
    """
    Función de conveniencia para limpiar el caché.
    
    Returns:
        int: Número de entradas eliminadas
    """
    cache = get_embedding_cache()
    return cache.clear()


def get_cache_stats() -> Dict[str, any]:
    """
    Función de conveniencia para obtener estadísticas del caché.
    
    Returns:
        dict: Estadísticas del caché
    """
    cache = get_embedding_cache()
    return cache.get_stats() 