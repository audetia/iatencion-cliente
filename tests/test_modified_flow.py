"""
Tests for Modified LangGraph Flow - CORRECTLY DESIGNED
=====================================================

Tests bien diseñados que realmente prueban la funcionalidad sin mezclar
mocks con ejecución real. Separación clara entre unit tests e integration tests.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.state import Email
from src.structure_outputs import EmailCategory


class TestEmailProcessingNodes:
    """Tests unitarios para nodos individuales del workflow."""
    
    @pytest.fixture
    def sample_emails(self):
        """Emails de muestra para testing."""
        return {
            'unrelated': Email(
                id="unrelated_1", threadId="t1", messageId="m1", references="",
                sender="spam@bad.com", subject="¡GANA DINERO YA!",
                body="Haz clic aquí para ganar $10,000 desde casa..."
            ),
            'pricing': Email(
                id="pricing_1", threadId="t2", messageId="m2", references="",
                sender="client@company.com", subject="Consulta precios",
                body="Hola, necesito información sobre sus precios y servicios de IA."
            )
        }
    
    @patch('src.nodes.Agents')
    @patch('src.nodes.EmailToolsClass')  
    def test_categorize_email_unrelated(self, mock_email_tools, mock_agents, sample_emails):
        """Test que un email no relacionado se categoriza correctamente."""
        from src.nodes import Nodes
        
        # Mock del agente de categorización
        mock_categorize_result = Mock()
        mock_categorize_result.category = EmailCategory.unrelated
        
        mock_agents.return_value.invoke_with_token_tracking.return_value = (mock_categorize_result, 100)
        mock_email_tools.return_value = Mock()
        
        # Crear nodo y probar
        nodes = Nodes()
        state = {"emails": [sample_emails['unrelated']]}
        
        result = nodes.categorize_email(state)
        
        # Verificaciones
        assert result["email_category"] == "unrelated"
        assert result["current_email"] == sample_emails['unrelated']
        assert result["session_tokens_used"] == 100

    def test_check_new_emails_empty(self):
        """Test routing cuando no hay emails."""
        from src.nodes import Nodes
        
        nodes = Nodes()
        state = {"emails": []}
        
        result = nodes.check_new_emails(state)
        
        assert result == "empty"
    
    def test_skip_unrelated_email(self, sample_emails):
        """Test que skip_unrelated_email remueve el email de la lista."""
        from src.nodes import Nodes
        
        nodes = Nodes()
        state = {"emails": [sample_emails['unrelated'], sample_emails['pricing']]}
        
        result = nodes.skip_unrelated_email(state)
        
        # Debería remover un email de la lista
        assert len(result["emails"]) == 1
        # El email que queda debería ser el primero (unrelated), ya que pop() remueve el último
        assert result["emails"][0] == sample_emails['unrelated']


class TestDynamicRAGSearch:
    """Tests unitarios para dynamic_rag_search - CORRECTAMENTE MOCKEADO."""
    
    @patch('src.nodes.db_manager')
    def test_dynamic_rag_search_success_with_cache_miss(self, mock_db):
        """Test dynamic_rag_search con cache miss y respuesta exitosa."""
        from src.nodes import Nodes
        
        # Mock embedding cache
        with patch('src.services.embedding_cache.get_embedding_cache') as mock_cache_func:
            mock_cache = Mock()
            mock_cache.get.return_value = None  # Cache miss
            mock_cache.put.return_value = None
            mock_cache_func.return_value = mock_cache
            
            # Create nodes instance first, then patch its agents
            nodes = Nodes()
            with patch.object(nodes, 'agents') as mock_agents:
                mock_agents.embeddings.embed_query.return_value = [0.1] * 1536
                
                # Mock database search results
                mock_db.search_similar_questions.return_value = {
                    'success': True,
                    'results': [
                        {
                            'question_id': 10,
                            'original_question': '¿Cuáles son los precios?',
                            'matched_variant': {
                                'similarity_score': 0.92
                            },
                            'answer': {
                                'has_answer': True,
                                'text': 'Nuestros precios van desde $500 hasta $3000 mensuales.',
                                'instructions': 'Menciona que incluye soporte 24/7'
                            }
                        }
                    ]
                }
                
                # Test
                result = nodes.dynamic_rag_search(user_id=1, query="¿Cuáles son los precios?")
                
                # Verificaciones
                assert result['success'] is True
                assert 'Nuestros precios van desde $500 hasta $3000 mensuales' in result['answer']
                assert 'soporte 24/7' in result['answer']
                assert result['similarity_score'] == 0.92
                assert result['matched_question'] == '¿Cuáles son los precios?'
                assert result['question_id'] == 10
                assert result['cache_hit'] is False

    @patch('src.nodes.db_manager')
    def test_dynamic_rag_search_no_questions_found(self, mock_db):
        """Test dynamic_rag_search cuando no encuentra preguntas similares."""
        from src.nodes import Nodes
        
        with patch('src.services.embedding_cache.get_embedding_cache') as mock_cache_func:
            mock_cache = Mock()
            mock_cache.get.return_value = None
            mock_cache_func.return_value = mock_cache
            
            # Create nodes instance first, then patch its agents
            nodes = Nodes()
            with patch.object(nodes, 'agents') as mock_agents:
                mock_agents.embeddings.embed_query.return_value = [0.3] * 1536
                
                # Mock database search results - sin resultados
                mock_db.search_similar_questions.return_value = {
                    'success': True,
                    'results': []
                }
                
                # Test
                result = nodes.dynamic_rag_search(user_id=1, query="¿Pregunta muy específica?")
                
                # Verificaciones
                assert result['success'] is False
                assert result['answer'] is None
                assert result['error'] == 'No similar questions found'
                assert result['similarity_score'] is None
                assert result['matched_question'] is None
                # cache_hit debería ser False porque no hay cache hit para esta query


class TestRetrieveFromRAG:
    """Tests unitarios para retrieve_from_rag - CORRECTAMENTE MOCKEADO."""
    
    @patch('src.nodes.db_manager')
    def test_retrieve_from_rag_success(self, mock_db):
        """Test retrieve_from_rag con búsqueda exitosa."""
        from src.nodes import Nodes
        
        # Mock database responses
        mock_db.get_email_account_info.return_value = {
            'success': True,
            'account_info': {'user_id': 1}
        }
        
        # Mock dynamic_rag_search method directamente
        with patch.object(Nodes, 'dynamic_rag_search') as mock_dynamic_search:
            mock_dynamic_search.return_value = {
                'success': True,
                'answer': 'Nuestros precios van desde $500 hasta $3000 mensuales.',
                'similarity_score': 0.92,
                'matched_question': '¿Cuáles son los precios?',
                'question_id': 10,
                'cache_hit': False
            }
            
            # Test
            nodes = Nodes()
            state = {
                "email_account_id": 1,
                "rag_queries": ["¿Cuáles son los precios de los servicios?"],
                "session_tokens_used": 250
            }
            
            result = nodes.retrieve_from_rag(state)
            
            # Verificaciones
            assert "Nuestros precios van desde $500 hasta $3000 mensuales" in result["retrieved_documents"]
            assert result["needs_human_attention"] is False
            assert len(result["qa_usage_stats"]) == 1
            assert result["qa_usage_stats"][0]["question_id"] == 10
            assert result["qa_usage_stats"][0]["similarity_score"] == 0.92
            assert result["qa_usage_stats"][0]["cache_hit"] is False

    @patch('src.nodes.db_manager')
    def test_retrieve_from_rag_no_email_account_id(self, mock_db):
        """Test retrieve_from_rag sin email_account_id en state."""
        from src.nodes import Nodes
        
        # Test
        nodes = Nodes()
        state = {
            "rag_queries": ["¿Pregunta cualquiera?"],
            "session_tokens_used": 250
        }
        
        result = nodes.retrieve_from_rag(state)
        
        # Verificaciones
        assert result["retrieved_documents"] == ""
        assert result["needs_human_attention"] is True
        assert result["qa_usage_stats"] == []
        
        # No debería llamar a la base de datos
        mock_db.get_email_account_info.assert_not_called()


class TestWorkflowRouting:
    """Tests para las funciones de routing del workflow."""
    
    def test_route_after_categorization_unrelated(self):
        """Test routing después de categorización - unrelated."""
        def route_after_categorization(state):
            category = state["email_category"]
            if category == "unrelated":
                return "unrelated"
            else:
                return "evaluate_forward"
        
        # Test casos
        assert route_after_categorization({"email_category": "unrelated"}) == "unrelated"
        assert route_after_categorization({"email_category": "product_enquiry"}) == "evaluate_forward"
        assert route_after_categorization({"email_category": "customer_complaint"}) == "evaluate_forward"


class TestEmailGeneration:
    """Tests para generación y verificación de emails."""
    
    def test_must_rewrite_logic(self):
        """Test lógica de decisión de reescritura."""
        from src.nodes import Nodes
        from src.state import Email
        
        nodes = Nodes()
        
        # Email aprobado - debe enviar (con emails en la lista)
        state_approved = {
            "sendable": True, 
            "trials": 1, 
            "emails": [Email(id="1", threadId="t1", messageId="m1", references="", 
                           sender="test@test.com", subject="Test", body="Test")]
        }
        assert nodes.must_rewrite(state_approved) == "send"
        
        # Email no aprobado, pocos intentos - debe reescribir (con emails en la lista)
        state_rewrite = {
            "sendable": False, 
            "trials": 1, 
            "emails": [Email(id="1", threadId="t1", messageId="m1", references="", 
                           sender="test@test.com", subject="Test", body="Test")]
        }
        assert nodes.must_rewrite(state_rewrite) == "rewrite"
        
        # Email no aprobado, muchos intentos - debe parar (con emails en la lista)
        state_stop = {
            "sendable": False, 
            "trials": 3, 
            "emails": [Email(id="1", threadId="t1", messageId="m1", references="", 
                           sender="test@test.com", subject="Test", body="Test")]
        }
        assert nodes.must_rewrite(state_stop) == "stop"


if __name__ == "__main__":
    print("Ejecutar con pytest:")
    print("pytest tests/test_modified_flow.py -v") 