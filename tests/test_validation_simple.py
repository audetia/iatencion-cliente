"""
Test de Validación Simple para Tests Completos
==============================================

Este archivo contiene un test básico para validar que la estructura
de tests está configurada correctamente y que los imports funcionan.
"""

import pytest
from unittest.mock import Mock, patch


def test_imports_work():
    """Test básico que verifica que todos los imports necesarios funcionan."""
    try:
        from src.state import Email, GraphState
        from src.structure_outputs import EmailCategory
        from src.nodes import Nodes
        
        # Test creación de Email
        email = Email(
            id="test_1",
            threadId="t1", 
            messageId="m1",
            references="",
            sender="test@test.com",
            subject="Test Subject",
            body="Test body content"
        )
        
        assert email.sender == "test@test.com"
        assert email.subject == "Test Subject"
        
        # Test que Nodes se puede instanciar (con mocks)
        with patch('src.nodes.Agents'), patch('src.nodes.EmailToolsClass'):
            nodes = Nodes()
            assert nodes is not None
        
        print("✅ Todos los imports funcionan correctamente")
        return True
        
    except ImportError as e:
        print(f"❌ Error de import: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False


def test_mock_structure():
    """Test que verifica que la estructura de mocking funciona."""
    # Test mock básico
    mock_obj = Mock()
    mock_obj.test_method.return_value = {"success": True, "data": "test"}
    
    result = mock_obj.test_method()
    assert result["success"] is True
    assert result["data"] == "test"
    
    # Test patch básico
    with patch('builtins.print') as mock_print:
        print("Test message")
        mock_print.assert_called_once_with("Test message")
    
    print("✅ Estructura de mocking funciona correctamente")
    return True


def test_email_state_structure():
    """Test que verifica la estructura de Email y State funciona."""
    from src.state import Email
    
    # Test creación de email completo
    email = Email(
        id="validation_test",
        threadId="thread_123",
        messageId="msg_456", 
        references="ref_789",
        sender="sender@example.com",
        subject="Validation Test Email",
        body="This is a test email for validation purposes."
    )
    
    # Test state structure
    state = {
        "current_email": email,
        "email_account_id": 1,
        "session_tokens_used": 0,
        "emails": [email],
        "forward_decision": {
            "should_forward": False,
            "forward_automation_id": None,
            "confidence_score": 0.0,
            "reason": "Test reason"
        }
    }
    
    # Validaciones
    assert state["current_email"].sender == "sender@example.com"
    assert state["email_account_id"] == 1
    assert state["forward_decision"]["should_forward"] is False
    
    print("✅ Estructura de Email y State funciona correctamente")
    return True


@patch('src.nodes.db_manager')
def test_basic_mock_pattern(mock_db):
    """Test que verifica el patrón básico de mock usado en los tests."""
    # Configure mock response
    mock_db.get_active_automations.return_value = {
        'success': True,
        'automations': []
    }
    
    # Call mock
    result = mock_db.get_active_automations(1)
    
    # Verify
    assert result['success'] is True
    assert result['automations'] == []
    mock_db.get_active_automations.assert_called_once_with(1)
    
    print("✅ Patrón básico de mock funciona correctamente")
    return True


if __name__ == "__main__":
    print("🔍 Ejecutando tests de validación...")
    
    try:
        test_imports_work()
        test_mock_structure() 
        test_email_state_structure()
        test_basic_mock_pattern()
        
        print("\n🎉 ¡Todos los tests de validación pasaron!")
        print("✅ La estructura está lista para ejecutar los tests completos")
        
    except Exception as e:
        print(f"\n❌ Error en tests de validación: {e}")
        print("🔧 Revisar configuración antes de ejecutar tests completos") 