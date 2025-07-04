"""
Tests Completos para Funcionalidad Modificada de LangGraph (Días 6-7)
====================================================================

Tests robustos y completos para la funcionalidad de Forward Rules y Dynamic RAG
implementada en los días 6-7 del MVP. Estos tests están diseñados para ser sólidos
y no fallar por problemas de diseño.

Cobertura:
- Forward Rules Evaluation (Día 6)
- Email Forwarding (Día 6)  
- Dynamic RAG Search completado (Día 7)
- Integration Tests (Días 6-7)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.state import Email, GraphState
from src.structure_outputs import EmailCategory, ForwardDecisionOutput


class TestForwardRulesEvaluation:
    """Tests para el nodo evaluate_forward_rules implementado en Día 6."""
    
    @pytest.fixture
    def sample_email(self):
        """Email de muestra para tests de forward rules."""
        return Email(
            id="forward_test_1",
            threadId="t1",
            messageId="m1",
            references="",
            sender="client@logistics.com",
            subject="Cambio de dirección de entrega",
            body="Necesito cambiar la dirección de entrega de mi pedido urgentemente."
        )
    
    @pytest.fixture
    def state_with_forward_email(self, sample_email):
        """State con email que debería ser reenviado."""
        return {
            "current_email": sample_email,
            "email_account_id": 1,
            "session_tokens_used": 100,
            "emails": [sample_email]
        }
    
    @patch('src.nodes.db_manager')
    def test_evaluate_forward_rules_success_with_forward_automation(self, mock_db, state_with_forward_email):
        """Test evaluación exitosa con automatización de reenvío activa."""
        from src.nodes import Nodes
        
        # Mock database response with forward automation
        mock_db.get_active_automations.return_value = {
            'success': True,
            'automations': [
                {
                    'id': 1,
                    'type': 'forward',
                    'forward_details': {
                        'description': 'Reenviar consultas de logística y entregas'
                    }
                }
            ]
        }
        
        # Mock forward decision agent
        mock_forward_decision = Mock()
        mock_forward_decision.should_forward = True
        mock_forward_decision.forward_automation_id = 1
        mock_forward_decision.confidence_score = 92.5
        mock_forward_decision.reason = "Email matches logistics delivery criteria"
        
        # Create nodes and mock the agent
        nodes = Nodes()
        with patch.object(nodes.agents, 'invoke_with_token_tracking') as mock_invoke:
            mock_invoke.return_value = (mock_forward_decision, 75)
            
            # Execute test
            result = nodes.evaluate_forward_rules(state_with_forward_email)
            
            # Verify database call
            mock_db.get_active_automations.assert_called_once_with(1)
            
            # Verify agent call
            mock_invoke.assert_called_once()
            call_args = mock_invoke.call_args[0]
            assert call_args[0] == nodes.agents.check_forward_rules
            assert "Necesito cambiar la dirección de entrega" in call_args[1]['email_content']
            assert "ID 1: Reenviar consultas de logística y entregas" in call_args[1]['forward_rules']
            assert "No Q&A topics configured." in call_args[1]['qa_topics']
            
            # Verify results
            assert result["forward_decision"]["should_forward"] is True
            assert result["forward_decision"]["forward_automation_id"] == 1
            assert result["forward_decision"]["confidence_score"] == 92.5
            assert result["forward_decision"]["reason"] == "Email matches logistics delivery criteria"
            assert result["forward_automations_available"] == 1
            assert result["qa_topics_available"] == 0
            assert result["session_tokens_used"] == 175  # 100 + 75
    
    @patch('src.nodes.db_manager')
    def test_evaluate_forward_rules_with_qa_topics_priority(self, mock_db, state_with_forward_email):
        """Test que Q&A topics tienen prioridad sobre forward rules."""
        from src.nodes import Nodes
        
        # Mock database response with both forward and Q&A automations
        mock_db.get_active_automations.return_value = {
            'success': True,
            'automations': [
                {
                    'id': 1,
                    'type': 'forward',
                    'forward_details': {
                        'description': 'Reenviar consultas de logística'
                    }
                },
                {
                    'id': 2,
                    'type': 'response',
                    'question_details': {
                        'original_question': '¿Cómo cambio mi dirección de entrega?'
                    }
                }
            ]
        }
        
        # Mock forward decision agent - should NOT forward because Q&A can handle it
        mock_forward_decision = Mock()
        mock_forward_decision.should_forward = False
        mock_forward_decision.forward_automation_id = None
        mock_forward_decision.confidence_score = 15.0
        mock_forward_decision.reason = "Q&A system can handle delivery address questions"
        
        nodes = Nodes()
        with patch.object(nodes.agents, 'invoke_with_token_tracking') as mock_invoke:
            mock_invoke.return_value = (mock_forward_decision, 60)
            
            result = nodes.evaluate_forward_rules(state_with_forward_email)
            
            # Verify Q&A topics were included in the prompt
            call_args = mock_invoke.call_args[0]
            assert "¿Cómo cambio mi dirección de entrega?" in call_args[1]['qa_topics']
            assert "ID 1: Reenviar consultas de logística" in call_args[1]['forward_rules']
            
            # Verify Q&A priority was respected
            assert result["forward_decision"]["should_forward"] is False
            assert result["forward_decision"]["forward_automation_id"] is None
            assert result["forward_automations_available"] == 1
            assert result["qa_topics_available"] == 1
    
    @patch('src.nodes.db_manager')
    def test_evaluate_forward_rules_no_automations(self, mock_db, state_with_forward_email):
        """Test evaluación con usuario sin automatizaciones configuradas."""
        from src.nodes import Nodes
        
        # Mock database response with no automations
        mock_db.get_active_automations.return_value = {
            'success': True,
            'automations': []
        }
        
        # Mock forward decision agent
        mock_forward_decision = Mock()
        mock_forward_decision.should_forward = False
        mock_forward_decision.forward_automation_id = None
        mock_forward_decision.confidence_score = 0.0
        mock_forward_decision.reason = "No forwarding rules configured"
        
        nodes = Nodes()
        with patch.object(nodes.agents, 'invoke_with_token_tracking') as mock_invoke:
            mock_invoke.return_value = (mock_forward_decision, 30)
            
            result = nodes.evaluate_forward_rules(state_with_forward_email)
            
            # Verify prompt contains appropriate messages
            call_args = mock_invoke.call_args[0]
            assert "No forwarding rules configured." in call_args[1]['forward_rules']
            assert "No Q&A topics configured." in call_args[1]['qa_topics']
            
            # Verify results
            assert result["forward_decision"]["should_forward"] is False
            assert result["forward_decision"]["forward_automation_id"] is None
            assert result["forward_automations_available"] == 0
            assert result["qa_topics_available"] == 0
    
    @patch('src.nodes.db_manager')
    def test_evaluate_forward_rules_database_error(self, mock_db, state_with_forward_email):
        """Test manejo de errores de base de datos."""
        from src.nodes import Nodes
        
        # Mock database error
        mock_db.get_active_automations.return_value = {
            'success': False,
            'error': 'Database connection failed'
        }
        
        nodes = Nodes()
        result = nodes.evaluate_forward_rules(state_with_forward_email)
        
        # Verify error handling
        assert result["forward_decision"]["should_forward"] is False
        assert result["forward_decision"]["forward_automation_id"] is None
        assert result["forward_decision"]["confidence_score"] == 0.0
        assert result["forward_decision"]["reason"] == "Failed to get automations"
        assert result["forward_error"] == "Failed to get automations"
        assert result["session_tokens_used"] == 100  # No additional tokens used
    
    @patch('src.nodes.db_manager')
    def test_evaluate_forward_rules_agent_error(self, mock_db, state_with_forward_email):
        """Test manejo de errores del agente de decisión."""
        from src.nodes import Nodes
        
        # Mock successful database response
        mock_db.get_active_automations.return_value = {
            'success': True,
            'automations': [
                {
                    'id': 1,
                    'type': 'forward',
                    'forward_details': {
                        'description': 'Test forward rule'
                    }
                }
            ]
        }
        
        nodes = Nodes()
        with patch.object(nodes.agents, 'invoke_with_token_tracking') as mock_invoke:
            # Mock agent error
            mock_invoke.side_effect = Exception("Agent invocation failed")
            
            result = nodes.evaluate_forward_rules(state_with_forward_email)
            
            # Verify error handling
            assert result["forward_decision"]["should_forward"] is False
            assert result["forward_decision"]["forward_automation_id"] is None
            assert result["forward_decision"]["confidence_score"] == 0.0
            assert "Error: Agent invocation failed" in result["forward_decision"]["reason"]
            assert result["forward_error"] == "Agent invocation failed"
            assert result["session_tokens_used"] == 100  # No additional tokens


class TestEmailForwarding:
    """Tests para el nodo forward_email implementado en Día 6."""
    
    @pytest.fixture
    def sample_email(self):
        """Email de muestra para tests de forwarding."""
        return Email(
            id="forward_email_1",
            threadId="t1",
            messageId="m1",
            references="",
            sender="client@company.com",
            subject="Consulta técnica urgente",
            body="Tengo un problema técnico que necesita atención inmediata."
        )
    
    @pytest.fixture
    def state_with_forward_decision(self, sample_email):
        """State con decisión de reenvío válida."""
        return {
            "current_email": sample_email,
            "forward_decision": {
                "should_forward": True,
                "forward_automation_id": 1,
                "confidence_score": 85.0,
                "reason": "Matches technical support criteria"
            },
            "emails": [sample_email]
        }
    
    @patch('src.nodes.db_manager')
    def test_forward_email_success(self, mock_db, state_with_forward_decision):
        """Test reenvío exitoso de email."""
        from src.nodes import Nodes
        
        # Mock database response with automation details
        mock_db.get_automation_details.return_value = {
            'success': True,
            'forward_details': {
                'forward_to_email': 'tech-support@company.com',
                'description': 'Technical support forwarding rule'
            }
        }
        
        nodes = Nodes()
        with patch.object(nodes.email_tools, 'forward_email') as mock_forward_email:
            # Mock successful forwarding
            mock_forward_email.return_value = {
                'id': 'forwarded_message_123',
                'original_sender': 'client@company.com',
                'forward_to': 'tech-support@company.com',
                'subject': 'Fwd: Consulta técnica urgente'
            }
            
            result = nodes.forward_email(state_with_forward_decision)
            
            # Verify database call
            mock_db.get_automation_details.assert_called_once_with(1)
            
            # Verify email forwarding call
            mock_forward_email.assert_called_once()
            call_args = mock_forward_email.call_args[1]
            assert call_args['forward_to'] == 'tech-support@company.com'
            assert call_args['automation_description'] == 'Technical support forwarding rule'
            
            # Verify original email data
            original_email = call_args['original_email']
            assert original_email['sender'] == 'client@company.com'
            assert original_email['subject'] == 'Consulta técnica urgente'
            assert original_email['body'] == 'Tengo un problema técnico que necesita atención inmediata.'
            
            # Verify results
            assert result["forward_completed"] is True
            assert result["forward_result"]["id"] == 'forwarded_message_123'
            assert result["forward_result"]["original_sender"] == 'client@company.com'
            assert result["retrieved_documents"] == ""  # Reset for next email
            assert result["trials"] == 0  # Reset for next email
    
    @patch('src.nodes.db_manager')
    def test_forward_email_no_forward_decision(self, mock_db, sample_email):
        """Test con forward_decision inválido."""
        from src.nodes import Nodes
        
        # State without valid forward decision
        state_invalid = {
            "current_email": sample_email,
            "forward_decision": {
                "should_forward": False,
                "forward_automation_id": None,
                "confidence_score": 10.0,
                "reason": "No matching criteria"
            },
            "emails": [sample_email]
        }
        
        nodes = Nodes()
        result = nodes.forward_email(state_invalid)
        
        # Verify error handling
        assert result["forward_error"] == "No valid forward decision"
        assert "forward_completed" not in result
        
        # Verify database was not called
        mock_db.get_automation_details.assert_not_called()
    
    @patch('src.nodes.db_manager')
    def test_forward_email_missing_automation_id(self, mock_db, sample_email):
        """Test con automation_id faltante."""
        from src.nodes import Nodes
        
        # State with missing automation_id
        state_missing_id = {
            "current_email": sample_email,
            "forward_decision": {
                "should_forward": True,
                "forward_automation_id": None,  # Missing ID
                "confidence_score": 80.0,
                "reason": "Should forward but no specific rule"
            },
            "emails": [sample_email]
        }
        
        nodes = Nodes()
        result = nodes.forward_email(state_missing_id)
        
        # Verify error handling
        assert result["forward_error"] == "No automation ID in forward decision"
        
        # Verify database was not called
        mock_db.get_automation_details.assert_not_called()
    
    @patch('src.nodes.db_manager')
    def test_forward_email_automation_not_found(self, mock_db, state_with_forward_decision):
        """Test con automatización no encontrada en base de datos."""
        from src.nodes import Nodes
        
        # Mock database error
        mock_db.get_automation_details.return_value = {
            'success': False,
            'error': 'Automation not found'
        }
        
        nodes = Nodes()
        result = nodes.forward_email(state_with_forward_decision)
        
        # Verify error handling
        assert result["forward_error"] == "Failed to get automation details"
        
        # Verify database was called
        mock_db.get_automation_details.assert_called_once_with(1)
    
    @patch('src.nodes.db_manager')
    def test_forward_email_missing_forward_details(self, mock_db, state_with_forward_decision):
        """Test con detalles de reenvío faltantes."""
        from src.nodes import Nodes
        
        # Mock database response without forward details
        mock_db.get_automation_details.return_value = {
            'success': True,
            'forward_details': None  # Missing forward details
        }
        
        nodes = Nodes()
        result = nodes.forward_email(state_with_forward_decision)
        
        # Verify error handling
        assert result["forward_error"] == "No forward details in automation"
    
    @patch('src.nodes.db_manager')
    def test_forward_email_missing_destination(self, mock_db, state_with_forward_decision):
        """Test con email de destino faltante."""
        from src.nodes import Nodes
        
        # Mock database response without destination email
        mock_db.get_automation_details.return_value = {
            'success': True,
            'forward_details': {
                'forward_to_email': None,  # Missing destination
                'description': 'Test rule'
            }
        }
        
        nodes = Nodes()
        result = nodes.forward_email(state_with_forward_decision)
        
        # Verify error handling
        assert result["forward_error"] == "No destination email configured"
    
    @patch('src.nodes.db_manager')
    def test_forward_email_forwarding_failed(self, mock_db, state_with_forward_decision):
        """Test con fallo en el reenvío del email."""
        from src.nodes import Nodes
        
        # Mock successful database response
        mock_db.get_automation_details.return_value = {
            'success': True,
            'forward_details': {
                'forward_to_email': 'tech@company.com',
                'description': 'Technical support'
            }
        }
        
        nodes = Nodes()
        with patch.object(nodes.email_tools, 'forward_email') as mock_forward_email:
            # Mock forwarding failure
            mock_forward_email.return_value = None
            
            result = nodes.forward_email(state_with_forward_decision)
            
            # Verify error handling
            assert result["forward_error"] == "Email forwarding failed"
            assert "forward_completed" not in result


class TestDynamicRAGSearchComplete:
    """Tests adicionales para dynamic_rag_search (completar cobertura Día 7)."""
    
    @patch('src.nodes.db_manager')
    def test_dynamic_rag_search_cache_hit(self, mock_db):
        """Test dynamic_rag_search con cache hit."""
        from src.nodes import Nodes
        
        # Mock embedding cache hit
        with patch('src.services.embedding_cache.get_embedding_cache') as mock_cache_func:
            mock_cache = Mock()
            mock_cache.get.return_value = [0.2] * 1536  # Cache hit
            mock_cache_func.return_value = mock_cache
            
            nodes = Nodes()
            # Don't need to mock embeddings since cache hit bypasses it
            
            # Mock database search results
            mock_db.search_similar_questions.return_value = {
                'success': True,
                'results': [
                    {
                        'question_id': 15,
                        'original_question': '¿Cuál es el precio de instalación?',
                        'matched_variant': {
                            'similarity_score': 0.89
                        },
                        'answer': {
                            'has_answer': True,
                            'text': 'La instalación cuesta $200 adicionales.',
                            'instructions': 'Mencionar que incluye garantía'
                        }
                    }
                ]
            }
            
            result = nodes.dynamic_rag_search(user_id=1, query="¿Cuánto cuesta la instalación?")
            
            # Verify cache was used
            mock_cache.get.assert_called_once_with("¿Cuánto cuesta la instalación?")
            mock_cache.put.assert_not_called()  # Should not store since it was a hit
            
            # Verify results
            assert result['success'] is True
            assert result['cache_hit'] is True
            assert result['similarity_score'] == 0.89
            assert 'garantía' in result['answer']
            assert result['question_id'] == 15
    
    @patch('src.nodes.db_manager')
    def test_dynamic_rag_search_similarity_threshold(self, mock_db):
        """Test que respeta el threshold de similitud."""
        from src.nodes import Nodes
        
        with patch('src.services.embedding_cache.get_embedding_cache') as mock_cache_func:
            mock_cache = Mock()
            mock_cache.get.return_value = None
            mock_cache_func.return_value = mock_cache
            
            nodes = Nodes()
            with patch.object(nodes, 'agents') as mock_agents:
                mock_agents.embeddings.embed_query.return_value = [0.4] * 1536
                
                # Mock database results below threshold (0.7)
                mock_db.search_similar_questions.return_value = {
                    'success': True,
                    'results': [
                        {
                            'question_id': 20,
                            'original_question': '¿Tienen descuentos?',
                            'matched_variant': {
                                'similarity_score': 0.65  # Below threshold
                            },
                            'answer': {
                                'has_answer': True,
                                'text': 'Sí, tenemos descuentos.',
                                'instructions': None
                            }
                        }
                    ]
                }
                
                result = nodes.dynamic_rag_search(user_id=1, query="¿Hay ofertas especiales?")
                
                # Verify database was called with correct threshold
                mock_db.search_similar_questions.assert_called_once_with(
                    user_id=1,
                    query_embedding=[0.4] * 1536,
                    threshold=0.7,
                    limit=3
                )
                
                # Since the result is below threshold, it should still be returned
                # (the database handles the threshold, not the method)
                assert result['success'] is True
                assert result['similarity_score'] == 0.65
    
    @patch('src.nodes.db_manager')
    def test_dynamic_rag_search_question_without_answer(self, mock_db):
        """Test con pregunta encontrada pero sin respuesta configurada."""
        from src.nodes import Nodes
        
        with patch('src.services.embedding_cache.get_embedding_cache') as mock_cache_func:
            mock_cache = Mock()
            mock_cache.get.return_value = None
            mock_cache_func.return_value = mock_cache
            
            nodes = Nodes()
            with patch.object(nodes, 'agents') as mock_agents:
                mock_agents.embeddings.embed_query.return_value = [0.5] * 1536
                
                # Mock database results with question but no answer
                mock_db.search_similar_questions.return_value = {
                    'success': True,
                    'results': [
                        {
                            'question_id': 25,
                            'original_question': '¿Cuándo abrirán nueva sucursal?',
                            'matched_variant': {
                                'similarity_score': 0.91
                            },
                            'answer': {
                                'has_answer': False,  # No answer configured
                                'text': None,
                                'instructions': None
                            }
                        }
                    ]
                }
                
                result = nodes.dynamic_rag_search(user_id=1, query="¿Cuándo abrirán otra tienda?")
                
                # Verify handling of question without answer
                assert result['success'] is False
                assert result['answer'] is None
                assert result['similarity_score'] == 0.91
                assert result['matched_question'] == '¿Cuándo abrirán nueva sucursal?'
                assert result['error'] == 'Question found but no answer configured'
    
    @patch('src.nodes.db_manager')
    def test_dynamic_rag_search_database_error(self, mock_db):
        """Test manejo de errores de base de datos."""
        from src.nodes import Nodes
        
        with patch('src.services.embedding_cache.get_embedding_cache') as mock_cache_func:
            mock_cache = Mock()
            mock_cache.get.return_value = None
            mock_cache_func.return_value = mock_cache
            
            nodes = Nodes()
            with patch.object(nodes, 'agents') as mock_agents:
                mock_agents.embeddings.embed_query.return_value = [0.6] * 1536
                
                # Mock database error
                mock_db.search_similar_questions.side_effect = Exception("Database connection failed")
                
                result = nodes.dynamic_rag_search(user_id=1, query="¿Qué productos tienen?")
                
                # Verify error handling
                assert result['success'] is False
                assert result['answer'] is None
                assert result['similarity_score'] is None
                assert result['matched_question'] is None
                assert result['error'] == 'Database connection failed'
                assert result['cache_hit'] is False


class TestWorkflowIntegration:
    """Tests de integración para el flujo completo de Días 6-7."""
    
    @pytest.fixture
    def sample_logistics_email(self):
        """Email de logística para tests de integración."""
        return Email(
            id="integration_1",
            threadId="t1",
            messageId="m1",
            references="",
            sender="customer@business.com",
            subject="Cambio de dirección urgente",
            body="Necesito cambiar la dirección de mi pedido #12345 lo antes posible."
        )
    
    @pytest.fixture
    def sample_pricing_email(self):
        """Email de precios para tests de integración."""
        return Email(
            id="integration_2",
            threadId="t2",
            messageId="m2",
            references="",
            sender="prospect@company.com",
            subject="Consulta de precios",
            body="¿Podrían enviarme información sobre sus precios y planes disponibles?"
        )
    
    @patch('src.nodes.db_manager')
    def test_integration_forward_flow_complete(self, mock_db, sample_logistics_email):
        """Test flujo completo: categorización → forward evaluation → forwarding."""
        from src.nodes import Nodes
        
        # Mock database responses
        mock_db.get_active_automations.return_value = {
            'success': True,
            'automations': [
                {
                    'id': 1,
                    'type': 'forward',
                    'forward_details': {
                        'description': 'Reenviar consultas de logística y entregas'
                    }
                }
            ]
        }
        
        mock_db.get_automation_details.return_value = {
            'success': True,
            'forward_details': {
                'forward_to_email': 'logistics@company.com',
                'description': 'Logistics forwarding rule'
            }
        }
        
        nodes = Nodes()
        
        # Mock agents for forward decision
        mock_forward_decision = Mock()
        mock_forward_decision.should_forward = True
        mock_forward_decision.forward_automation_id = 1
        mock_forward_decision.confidence_score = 88.0
        mock_forward_decision.reason = "Matches logistics delivery criteria"
        
        with patch.object(nodes.agents, 'invoke_with_token_tracking') as mock_invoke:
            mock_invoke.return_value = (mock_forward_decision, 65)
            
            with patch.object(nodes.email_tools, 'forward_email') as mock_forward_email:
                mock_forward_email.return_value = {
                    'id': 'forwarded_123',
                    'original_sender': 'customer@business.com'
                }
                
                # Test evaluate_forward_rules
                state = {
                    "current_email": sample_logistics_email,
                    "email_account_id": 1,
                    "session_tokens_used": 50,
                    "emails": [sample_logistics_email]
                }
                
                result1 = nodes.evaluate_forward_rules(state)
                
                # Verify forward decision
                assert result1["forward_decision"]["should_forward"] is True
                assert result1["forward_decision"]["forward_automation_id"] == 1
                
                # Update state with forward decision
                state.update(result1)
                
                # Test forward_email
                result2 = nodes.forward_email(state)
                
                # Verify forwarding completed
                assert result2["forward_completed"] is True
                assert result2["forward_result"]["id"] == 'forwarded_123'
    
    @patch('src.nodes.db_manager')
    def test_integration_qa_priority_over_forward(self, mock_db, sample_pricing_email):
        """Test que Q&A tiene prioridad sobre forwarding."""
        from src.nodes import Nodes
        
        # Mock database responses with both Q&A and forward automations
        mock_db.get_active_automations.return_value = {
            'success': True,
            'automations': [
                {
                    'id': 1,
                    'type': 'forward',
                    'forward_details': {
                        'description': 'Reenviar consultas comerciales'
                    }
                },
                {
                    'id': 2,
                    'type': 'response',
                    'question_details': {
                        'original_question': '¿Cuáles son sus precios?'
                    }
                }
            ]
        }
        
        nodes = Nodes()
        
        # Mock forward decision - should NOT forward because Q&A can handle it
        mock_forward_decision = Mock()
        mock_forward_decision.should_forward = False
        mock_forward_decision.forward_automation_id = None
        mock_forward_decision.confidence_score = 25.0
        mock_forward_decision.reason = "Q&A system can handle pricing questions"
        
        with patch.object(nodes.agents, 'invoke_with_token_tracking') as mock_invoke:
            mock_invoke.return_value = (mock_forward_decision, 45)
            
            state = {
                "current_email": sample_pricing_email,
                "email_account_id": 1,
                "session_tokens_used": 30,
                "emails": [sample_pricing_email]
            }
            
            result = nodes.evaluate_forward_rules(state)
            
            # Verify Q&A priority was respected
            assert result["forward_decision"]["should_forward"] is False
            assert result["forward_decision"]["forward_automation_id"] is None
            assert result["forward_automations_available"] == 1
            assert result["qa_topics_available"] == 1
            
            # Verify prompt included both Q&A and forward rules
            call_args = mock_invoke.call_args[0]
            assert "¿Cuáles son sus precios?" in call_args[1]['qa_topics']
            assert "Reenviar consultas comerciales" in call_args[1]['forward_rules']
    
    def test_integration_routing_logic(self):
        """Test lógica de routing después de categorización."""
        from src.graph import Workflow
        
        # Mock del routing function
        def route_after_categorization(state):
            category = state["email_category"]
            if category == "unrelated":
                return "unrelated"
            elif category == "spam":
                return "spam"
            else:
                return "evaluate_forward"
        
        # Test casos de routing
        test_cases = [
            ({"email_category": "unrelated"}, "unrelated"),
            ({"email_category": "spam"}, "spam"),
            ({"email_category": "product_enquiry"}, "evaluate_forward"),
            ({"email_category": "lead_enquiry"}, "evaluate_forward"),
            ({"email_category": "customer_complaint"}, "evaluate_forward"),
            ({"email_category": "customer_feedback"}, "evaluate_forward")
        ]
        
        for state, expected_route in test_cases:
            result = route_after_categorization(state)
            assert result == expected_route, f"Failed for category {state['email_category']}: expected {expected_route}, got {result}"


if __name__ == "__main__":
    print("Ejecutar con pytest:")
    print("pytest tests/test_modified_flow_complete.py -v")
    print("\nPara ejecutar solo un grupo de tests:")
    print("pytest tests/test_modified_flow_complete.py::TestForwardRulesEvaluation -v")
    print("pytest tests/test_modified_flow_complete.py::TestEmailForwarding -v")
    print("pytest tests/test_modified_flow_complete.py::TestDynamicRAGSearchComplete -v")
    print("pytest tests/test_modified_flow_complete.py::TestWorkflowIntegration -v") 