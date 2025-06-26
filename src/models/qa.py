"""
Modelos Question, QuestionVariant y Answer para el sistema de automatización de emails.

Este módulo define los modelos relacionados con preguntas y respuestas que
permiten a los usuarios configurar respuestas automáticas personalizadas.
"""

import csv
import io
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, text
from sqlalchemy.orm import relationship
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from typing import List, Optional, Dict, Union

from .base import Base, TimestampMixin
from ..agents import Agents
from ..database import db_manager


class Question(Base, TimestampMixin):
    """
    Modelo para preguntas originales creadas por usuarios.
    
    Representa una pregunta original que puede tener múltiples variantes
    para mejorar la detección semántica y una respuesta asociada.
    
    Attributes:
        id (int): Identificador único de la pregunta (clave primaria)
        user_id (int): ID del usuario que creó la pregunta (clave foránea)
        original_question (str): Texto original de la pregunta
        created_at (datetime): Fecha de creación (automática)
        updated_at (datetime): Fecha de última actualización (automática)
    
    Relationships:
        user: Usuario que creó la pregunta
        variants: Lista de variantes de la pregunta con embeddings
        answer: Respuesta asociada a la pregunta
        automation_questions: Relación con automatizaciones que usan esta pregunta
    """
    __tablename__ = 'question'
    
    # Campos principales
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    original_question = Column(Text, nullable=False)
    
    # Relaciones
    user = relationship("User", back_populates="questions")
    variants = relationship("QuestionVariant", back_populates="question", cascade="all, delete-orphan")
    answer = relationship("Answer", back_populates="question", uselist=False, cascade="all, delete-orphan")
    response_automation = relationship("ResponseAutomation", back_populates="question", uselist=False)
    
    def __repr__(self):
        """
        Representación string de la pregunta.
        
        Returns:
            str: Representación legible de la pregunta
        """
        return f"<Question(id={self.id}, user_id={self.user_id}, question='{self.original_question[:50]}...')>"
    
    def __str__(self):
        """
        String representation para uso general.
        
        Returns:
            str: Pregunta truncada para mostrar
        """
        return f"{self.original_question[:100]}{'...' if len(self.original_question) > 100 else ''}"
    
    @property
    def has_answer(self) -> bool:
        """
        Verifica si la pregunta tiene una respuesta asociada.
        
        Returns:
            bool: True si tiene respuesta
        """
        return self.answer is not None
    
    @property
    def variants_count(self) -> int:
        """
        Cuenta el número de variantes de la pregunta.
        
        Returns:
            int: Número de variantes
        """
        return len(self.variants) if self.variants else 0
    
    def to_dict(self) -> dict:
        """
        Convierte la pregunta a diccionario.
        
        Returns:
            dict: Representación de la pregunta como diccionario
        """
        return {
            'id': self.id,
            'user_id': self.user_id,
            'original_question': self.original_question,
            'has_answer': self.has_answer,
            'variants_count': self.variants_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    # =============================================================================
    # MÉTODOS DE CONSULTA (CLASS METHODS)
    # =============================================================================
    
    @classmethod
    def create(cls, db_session, user_id: int, original_question: str) -> 'Question':
        """
        Crea una nueva pregunta en la base de datos.
        Automáticamente añade la pregunta original como una variante.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            original_question (str): Texto de la pregunta original
            
        Returns:
            Question: Pregunta creada con su variante original
        """
        question = cls(user_id=user_id, original_question=original_question)
        db_session.add(question)
        db_session.flush()  # Necesario para obtener el ID
        
        # Añadir automáticamente la pregunta original como variante
        original_variant = QuestionVariant.create(db_session, question.id, original_question)
        
        return question
    
    @classmethod
    def import_from_csv(cls, db_session, user_id: int, csv_content: Union[str, io.StringIO]) -> Dict[str, Union[int, List[str]]]:
        """
        Importa múltiples Q&A desde contenido CSV.
        
        Formato CSV esperado: question,answer,response_instructions
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            csv_content (str | io.StringIO): Contenido CSV o stream
            
        Returns:
            dict: Resultado de la importación con estadísticas y errores
        """
        if isinstance(csv_content, str):
            csv_content = io.StringIO(csv_content)
        
        results = {
            'imported': 0,
            'errors': [],
            'skipped': 0,
            'total_processed': 0
        }
        
        try:
            csv_reader = csv.DictReader(csv_content)
            
            # Validar headers requeridos
            required_headers = {'question', 'answer'}
            if not required_headers.issubset(set(csv_reader.fieldnames or [])):
                results['errors'].append(f"Headers requeridos: {required_headers}")
                return results
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 for header
                results['total_processed'] += 1
                
                try:
                    question_text = row.get('question', '').strip()
                    answer_text = row.get('answer', '').strip()
                    response_instructions = row.get('response_instructions', '').strip() or None
                    
                    # Validaciones básicas
                    if not question_text or not answer_text:
                        results['errors'].append(f"Fila {row_num}: Pregunta y respuesta son requeridas")
                        results['skipped'] += 1
                        continue
                    
                    if len(question_text) > 1000 or len(answer_text) > 5000:
                        results['errors'].append(f"Fila {row_num}: Texto demasiado largo")
                        results['skipped'] += 1
                        continue
                    
                    # Crear pregunta y respuesta
                    question = cls.create(db_session, user_id, question_text)
                    Answer.create(db_session, question.id, answer_text, response_instructions)
                    
                    results['imported'] += 1
                    
                except Exception as e:
                    results['errors'].append(f"Fila {row_num}: {str(e)}")
                    results['skipped'] += 1
                    db_session.rollback()
                    continue
            
            # Commit solo si no hay errores críticos
            if results['imported'] > 0:
                db_session.commit()
            
        except Exception as e:
            results['errors'].append(f"Error procesando CSV: {str(e)}")
            db_session.rollback()
        
        return results
    
    @classmethod
    def get_by_id(cls, db_session, question_id: int) -> Optional['Question']:
        """
        Obtiene una pregunta por su ID.
        
        Args:
            db_session: Sesión de base de datos
            question_id (int): ID de la pregunta
            
        Returns:
            Question | None: Pregunta encontrada o None
        """
        return db_session.query(cls).filter(cls.id == question_id).first()
    
    @classmethod
    def get_by_user(cls, db_session, user_id: int) -> List['Question']:
        """
        Obtiene todas las preguntas de un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            
        Returns:
            List[Question]: Lista de preguntas del usuario
        """
        return db_session.query(cls).filter(cls.user_id == user_id).all()
    
    @classmethod
    def get_with_answers_by_user(cls, db_session, user_id: int) -> List['Question']:
        """
        Obtiene todas las preguntas con respuestas de un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            
        Returns:
            List[Question]: Lista de preguntas que tienen respuesta
        """
        return db_session.query(cls).filter(
            cls.user_id == user_id
        ).join(Answer).all()
    
    @classmethod
    def count_by_user(cls, db_session, user_id: int) -> int:
        """
        Cuenta las preguntas de un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            
        Returns:
            int: Total de preguntas del usuario
        """
        return db_session.query(cls).filter(cls.user_id == user_id).count()
    
    # =============================================================================
    # MÉTODOS DE INSTANCIA
    # =============================================================================
    
    def update(self, db_session, **kwargs) -> None:
        """
        Actualiza los campos de la pregunta.
        
        Args:
            db_session: Sesión de base de datos
            **kwargs: Campos a actualizar (original_question)
        """
        allowed_fields = {'original_question'}
        
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(self, field):
                setattr(self, field, value)
        
        db_session.flush()
    
    def delete(self, db_session) -> None:
        """
        Elimina la pregunta de la base de datos.
        
        Args:
            db_session: Sesión de base de datos
            
        Note:
            Esto también eliminará todas las variantes y respuesta asociadas
            debido al cascade="all, delete-orphan".
        """
        db_session.delete(self)
        db_session.flush()
    
    def add_variant(self, db_session, variant_text: str) -> 'QuestionVariant':
        """
        Añade una variante a la pregunta.
        
        Args:
            db_session: Sesión de base de datos
            variant_text (str): Texto de la variante
            
        Returns:
            QuestionVariant: La variante creada
        """
        variant = QuestionVariant.create(db_session, self.id, variant_text)
        return variant
    
    def get_variants_with_embeddings(self, db_session) -> List['QuestionVariant']:
        """
        Obtiene todas las variantes de la pregunta con embeddings.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            List[QuestionVariant]: Lista de variantes con embeddings
        """
        return db_session.query(QuestionVariant).filter(
            QuestionVariant.question_id == self.id
        ).all()


class QuestionVariant(Base):
    """
    Modelo para variantes de preguntas con embeddings vectoriales.
    
    Representa diferentes formas de hacer la misma pregunta, cada una
    con su embedding vectorial para búsqueda semántica.
    
    Attributes:
        id (int): Identificador único de la variante (clave primaria)
        question_id (int): ID de la pregunta original (clave foránea)
        variant_text (str): Texto de la variante
        embedding (vector): Vector de embedding para búsqueda semántica
        created_at (datetime): Fecha de creación (automática)
    
    Relationships:
        question: Pregunta original a la que pertenece esta variante
    """
    __tablename__ = 'question_variant'
    
    # Campos principales
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey('question.id'), nullable=False, index=True)
    variant_text = Column(Text, nullable=False)
    # El embedding se maneja como un campo especial en SQLAlchemy con pgvector
    embedding = Column('embedding', None, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relaciones
    question = relationship("Question", back_populates="variants")
    
    def __repr__(self):
        """
        Representación string de la variante.
        
        Returns:
            str: Representación legible de la variante
        """
        return f"<QuestionVariant(id={self.id}, question_id={self.question_id}, text='{self.variant_text[:50]}...')>"
    
    def __str__(self):
        """
        String representation para uso general.
        
        Returns:
            str: Texto de la variante truncado
        """
        return f"{self.variant_text[:100]}{'...' if len(self.variant_text) > 100 else ''}"
    
    @property
    def has_embedding(self) -> bool:
        """
        Verifica si la variante tiene embedding generado.
        
        Returns:
            bool: True si tiene embedding
        """
        return self.embedding is not None
    
    def to_dict(self) -> dict:
        """
        Convierte la variante a diccionario.
        
        Returns:
            dict: Representación de la variante como diccionario
        """
        return {
            'id': self.id,
            'question_id': self.question_id,
            'variant_text': self.variant_text,
            'has_embedding': self.has_embedding,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def validate_embedding(self, expected_dim: int = 1536) -> Dict[str, Union[bool, str]]:
        """
        Valida el formato y dimensionalidad del embedding.
        
        Args:
            expected_dim (int): Dimensionalidad esperada del embedding
            
        Returns:
            dict: Resultado de validación con detalles
        """
        if not self.embedding:
            return {'is_valid': False, 'error': 'No hay embedding'}
        
        try:
            # Convertir a lista si es necesario
            if isinstance(self.embedding, str):
                # Asumir formato de string de PostgreSQL: [1.0, 2.0, ...]
                embedding_list = eval(self.embedding)
            else:
                embedding_list = list(self.embedding)
            
            # Validar dimensionalidad
            if len(embedding_list) != expected_dim:
                return {
                    'is_valid': False, 
                    'error': f'Dimensionalidad incorrecta: {len(embedding_list)}, esperada: {expected_dim}'
                }
            
            # Validar que todos sean números
            if not all(isinstance(x, (int, float)) for x in embedding_list):
                return {'is_valid': False, 'error': 'Embedding contiene valores no numéricos'}
            
            # Validar rango razonable (embeddings normalizados suelen estar en [-1, 1])
            if any(abs(x) > 10 for x in embedding_list):
                return {'is_valid': False, 'error': 'Valores de embedding fuera de rango esperado'}
            
            return {'is_valid': True, 'error': None}
            
        except Exception as e:
            return {'is_valid': False, 'error': f'Error validando embedding: {str(e)}'}
    
    def validate_variant_quality(self, db_session, min_diversity: float = 0.15) -> Dict[str, Union[bool, str, float]]:
        """
        Valida que la variante no sea muy similar a otras existentes de la misma pregunta.
        
        Args:
            db_session: Sesión de base de datos
            min_diversity (float): Umbral mínimo de diversidad (0.0-1.0)
            
        Returns:
            dict: Resultado de validación con score de diversidad
        """
        if not self.has_embedding:
            return {'is_valid': False, 'error': 'No hay embedding para comparar', 'diversity_score': 0.0}
        
        try:
            # Obtener otras variantes de la misma pregunta
            other_variants = db_session.query(QuestionVariant).filter(
                QuestionVariant.question_id == self.question_id,
                QuestionVariant.id != self.id
            ).all()
            
            if not other_variants:
                return {'is_valid': True, 'error': None, 'diversity_score': 1.0}
            
            # Calcular similitud máxima con otras variantes
            max_similarity = 0.0
            for other in other_variants:
                if other.has_embedding:
                    similarity = self._calculate_cosine_similarity(self.embedding, other.embedding)
                    max_similarity = max(max_similarity, similarity)
            
            diversity_score = 1.0 - max_similarity
            is_diverse_enough = diversity_score >= min_diversity
            
            return {
                'is_valid': is_diverse_enough,
                'error': None if is_diverse_enough else f'Variante muy similar a existente (diversidad: {diversity_score:.3f})',
                'diversity_score': diversity_score
            }
            
        except Exception as e:
            return {'is_valid': False, 'error': f'Error validando diversidad: {str(e)}', 'diversity_score': 0.0}
    
    def _calculate_cosine_similarity(self, embedding1, embedding2) -> float:
        """
        Calcula similitud coseno entre dos embeddings.
        
        Args:
            embedding1, embedding2: Embeddings a comparar
            
        Returns:
            float: Similitud coseno (0.0-1.0)
        """
        try:
            import numpy as np
            
            # Convertir a arrays numpy
            vec1 = np.array(embedding1, dtype=np.float32)
            vec2 = np.array(embedding2, dtype=np.float32)
            
            # Calcular similitud coseno
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return float(dot_product / (norm1 * norm2))
            
        except Exception:
            return 0.0
    
    def generate_embedding(self) -> None:
        """
        Genera el embedding para la variante usando el modelo de embeddings.
        Debe llamarse antes de guardar la variante.
        
        Raises:
            ValueError: Si no hay texto para generar embedding
        """
        if not self.variant_text:
            raise ValueError("No se puede generar embedding para una variante sin texto")
            
        # Crear instancia del agente de embeddings
        agents = Agents()
        embeddings = agents.embeddings
        
        # Generar embedding con la dimensionalidad específica
        self.embedding = embeddings.embed_query(
            self.variant_text, 
            output_dimensionality=1536
        )
    
    # =============================================================================
    # MÉTODOS DE CONSULTA (CLASS METHODS)
    # =============================================================================
    
    @classmethod
    def create(cls, db_session, question_id: int, variant_text: str) -> 'QuestionVariant':
        """
        Crea una nueva variante con embedding en la base de datos.
        
        Args:
            db_session: Sesión de base de datos
            question_id (int): ID de la pregunta original
            variant_text (str): Texto de la variante
            
        Returns:
            QuestionVariant: Variante creada con embedding
        """
        variant = cls(question_id=question_id, variant_text=variant_text)
        variant.generate_embedding()
        db_session.add(variant)
        db_session.flush()
        return variant
    
    @classmethod
    def get_by_id(cls, db_session, variant_id: int) -> Optional['QuestionVariant']:
        """
        Obtiene una variante por su ID.
        
        Args:
            db_session: Sesión de base de datos
            variant_id (int): ID de la variante
            
        Returns:
            QuestionVariant | None: Variante encontrada o None
        """
        return db_session.query(cls).filter(cls.id == variant_id).first()
    
    @classmethod
    def get_by_question(cls, db_session, question_id: int) -> List['QuestionVariant']:
        """
        Obtiene todas las variantes de una pregunta.
        
        Args:
            db_session: Sesión de base de datos
            question_id (int): ID de la pregunta
            
        Returns:
            List[QuestionVariant]: Lista de variantes de la pregunta
        """
        return db_session.query(cls).filter(cls.question_id == question_id).all()
    
    @classmethod
    def search_similar(cls, db_session, user_id: int, query_embedding: List[float], 
                      threshold: float = 0.8, limit: int = 5) -> List[tuple]:
        """
        Busca variantes similares usando búsqueda vectorial con pgvector.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario para filtrar
            query_embedding (List[float]): Embedding de la consulta
            threshold (float): Umbral de similitud (0.0-1.0)
            limit (int): Número máximo de resultados
            
        Returns:
            List[tuple]: Lista de tuplas (QuestionVariant, similarity_score)
        """
        try:
            # Convertir embedding a formato PostgreSQL
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            # Query SQL nativo usando operador de similitud coseno de pgvector
            sql_query = text("""
                SELECT qv.*, q.user_id, (1 - (qv.embedding <=> :query_embedding)) as similarity
                FROM question_variants qv
                JOIN questions q ON qv.question_id = q.id
                WHERE q.user_id = :user_id
                AND (1 - (qv.embedding <=> :query_embedding)) >= :threshold
                ORDER BY qv.embedding <=> :query_embedding
                LIMIT :limit
            """)
            
            result = db_session.execute(sql_query, {
                'query_embedding': embedding_str,
                'user_id': user_id,
                'threshold': threshold,
                'limit': limit
            })
            
            # Procesar resultados
            similar_variants = []
            for row in result:
                # Reconstruir objeto QuestionVariant
                variant = cls()
                variant.id = row.id
                variant.question_id = row.question_id
                variant.variant_text = row.variant_text
                variant.embedding = row.embedding
                variant.created_at = row.created_at
                
                similarity_score = float(row.similarity)
                similar_variants.append((variant, similarity_score))
            
            return similar_variants
            
        except Exception as e:
            # Log error y retornar lista vacía como fallback
            print(f"Error en búsqueda vectorial: {e}")
            return []
    
    # =============================================================================
    # MÉTODOS DE INSTANCIA
    # =============================================================================
    
    def update(self, db_session, **kwargs) -> None:
        """
        Actualiza los campos de la variante.
        
        Args:
            db_session: Sesión de base de datos
            **kwargs: Campos a actualizar (variant_text)
        """
        allowed_fields = {'variant_text'}
        
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(self, field):
                setattr(self, field, value)
                # Si se actualiza el texto, regenerar embedding
                if field == 'variant_text':
                    self.generate_embedding()
        
        db_session.flush()
    
    def delete(self, db_session) -> None:
        """
        Elimina la variante de la base de datos.
        
        Args:
            db_session: Sesión de base de datos
        """
        db_session.delete(self)
        db_session.flush()


class Answer(Base, TimestampMixin):
    """
    Modelo para respuestas asociadas a preguntas.
    
    Representa la respuesta que se enviará automáticamente cuando
    se detecte una pregunta similar a través de las variantes.
    
    Attributes:
        id (int): Identificador único de la respuesta (clave primaria)
        question_id (int): ID de la pregunta asociada (clave foránea)
        answer_text (str): Texto de la respuesta
        response_instructions (str): Instrucciones adicionales para la respuesta
        created_at (datetime): Fecha de creación (automática)
        updated_at (datetime): Fecha de última actualización (automática)
    
    Relationships:
        question: Pregunta a la que responde esta respuesta
    """
    __tablename__ = 'answer'
    
    # Campos principales
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey('question.id'), nullable=False, unique=True, index=True)
    answer_text = Column(Text, nullable=False)
    response_instructions = Column(String(255))
    
    # Relaciones
    question = relationship("Question", back_populates="answer")
    
    def __repr__(self):
        """
        Representación string de la respuesta.
        
        Returns:
            str: Representación legible de la respuesta
        """
        return f"<Answer(id={self.id}, question_id={self.question_id}, answer='{self.answer_text[:50]}...')>"
    
    def __str__(self):
        """
        String representation para uso general.
        
        Returns:
            str: Respuesta truncada para mostrar
        """
        return f"{self.answer_text[:100]}{'...' if len(self.answer_text) > 100 else ''}"
    
    @property
    def has_instructions(self) -> bool:
        """
        Verifica si la respuesta tiene instrucciones adicionales.
        
        Returns:
            bool: True si tiene instrucciones
        """
        return bool(self.response_instructions)
    
    def to_dict(self) -> dict:
        """
        Convierte la respuesta a diccionario.
        
        Returns:
            dict: Representación de la respuesta como diccionario
        """
        return {
            'id': self.id,
            'question_id': self.question_id,
            'answer_text': self.answer_text,
            'response_instructions': self.response_instructions,
            'has_instructions': self.has_instructions,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    # =============================================================================
    # MÉTODOS DE CONSULTA (CLASS METHODS)
    # =============================================================================
    
    @classmethod
    def create(cls, db_session, question_id: int, answer_text: str, 
               response_instructions: str = None) -> 'Answer':
        """
        Crea una nueva respuesta en la base de datos.
        
        Args:
            db_session: Sesión de base de datos
            question_id (int): ID de la pregunta
            answer_text (str): Texto de la respuesta
            response_instructions (str, optional): Instrucciones adicionales
            
        Returns:
            Answer: Respuesta creada
            
        Raises:
            ValueError: Si ya existe una respuesta para esa pregunta
        """
        # Verificar si ya existe una respuesta para esta pregunta
        existing_answer = cls.get_by_question(db_session, question_id)
        if existing_answer:
            raise ValueError(f"Ya existe una respuesta para la pregunta ID: {question_id}")
        
        answer = cls(
            question_id=question_id,
            answer_text=answer_text,
            response_instructions=response_instructions
        )
        
        db_session.add(answer)
        db_session.flush()
        return answer
    
    @classmethod
    def get_by_id(cls, db_session, answer_id: int) -> Optional['Answer']:
        """
        Obtiene una respuesta por su ID.
        
        Args:
            db_session: Sesión de base de datos
            answer_id (int): ID de la respuesta
            
        Returns:
            Answer | None: Respuesta encontrada o None
        """
        return db_session.query(cls).filter(cls.id == answer_id).first()
    
    @classmethod
    def get_by_question(cls, db_session, question_id: int) -> Optional['Answer']:
        """
        Obtiene la respuesta de una pregunta específica.
        
        Args:
            db_session: Sesión de base de datos
            question_id (int): ID de la pregunta
            
        Returns:
            Answer | None: Respuesta encontrada o None
        """
        return db_session.query(cls).filter(cls.question_id == question_id).first()
    
    @classmethod
    def get_by_user(cls, db_session, user_id: int) -> List['Answer']:
        """
        Obtiene todas las respuestas de un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            
        Returns:
            List[Answer]: Lista de respuestas del usuario
        """
        return db_session.query(cls).join(Question).filter(
            Question.user_id == user_id
        ).all()
    
    # =============================================================================
    # MÉTODOS DE INSTANCIA
    # =============================================================================
    
    def update(self, db_session, **kwargs) -> None:
        """
        Actualiza los campos de la respuesta.
        
        Args:
            db_session: Sesión de base de datos
            **kwargs: Campos a actualizar (answer_text, response_instructions)
        """
        allowed_fields = {'answer_text', 'response_instructions'}
        
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(self, field):
                setattr(self, field, value)
        
        db_session.flush()
    
    def delete(self, db_session) -> None:
        """
        Elimina la respuesta de la base de datos.
        
        Args:
            db_session: Sesión de base de datos
        """
        db_session.delete(self)
        db_session.flush()
    
    def get_question_info(self, db_session) -> dict:
        """
        Obtiene información de la pregunta asociada.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            dict: Información de la pregunta
        """
        if self.question:
            return {
                'question_id': self.question.id,
                'original_question': self.question.original_question,
                'user_id': self.question.user_id,
                'variants_count': self.question.variants_count
            }
        return {}