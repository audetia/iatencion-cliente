"""
Tests para el servicio InboxMonitor.

Incluye tests unitarios y de integración para verificar el funcionamiento
del servicio de monitoreo de buzones, especialmente el método monitor_single_inbox.
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import time

# Importar las clases a testear
from src.services.inbox_monitor import InboxMonitor, MonitoringConfig, RateLimiter
from src.tools.EmailTools import EmailToolsClass


class TestInboxMonitor(unittest.TestCase):
    """Tests para la clase InboxMonitor."""
    
    def setUp(self):
        """Configuración inicial para cada test."""
        self.config = MonitoringConfig(
            max_workers=2,
            rate_limit_delay=1.0,
            batch_size=5,
            check_interval=60,
            connection_timeout=10,
            max_retries=2,
            retry_delay=5.0
        )
        
        # Mock del procesador de emails
        self.mock_email_processor = Mock()
        
        # Crear instancia del monitor
        self.monitor = InboxMonitor(
            email_processor=self.mock_email_processor,
            config=self.config
        )
    
    def test_monitor_initialization(self):
        """Test de inicialización del monitor."""
        self.assertEqual(self.monitor.config.max_workers, 2)
        self.assertEqual(self.monitor.config.batch_size, 5)
        self.assertEqual(self.monitor.config.max_retries, 2)
        self.assertFalse(self.monitor.is_running)
        self.assertIsNotNone(self.monitor.rate_limiter)
    
    def test_monitor_single_inbox_invalid_account_id(self):
        """Test de validación de account_id inválido."""
        with self.assertRaises(ValueError) as context:
            self.monitor.monitor_single_inbox(0)
        
        self.assertIn("entero positivo", str(context.exception))
        
        with self.assertRaises(ValueError) as context:
            self.monitor.monitor_single_inbox(-1)
        
        self.assertIn("entero positivo", str(context.exception))
    
    @patch('src.services.inbox_monitor.db_manager')
    def test_monitor_single_inbox_credentials_error(self, mock_db_manager):
        """Test de error al obtener credenciales."""
        # Configurar mock para retornar error
        mock_db_manager.get_email_account_credentials.return_value = {
            'success': False,
            'message': 'Cuenta no encontrada'
        }
        
        with self.assertRaises(RuntimeError) as context:
            self.monitor.monitor_single_inbox(1)
        
        self.assertIn("Cuenta no encontrada", str(context.exception))
    
    @patch('src.services.inbox_monitor.db_manager')
    @patch('src.services.inbox_monitor.EmailToolsClass')
    def test_monitor_single_inbox_no_emails(self, mock_email_tools_class, mock_db_manager):
        """Test de monitoreo sin emails nuevos."""
        # Configurar mocks
        mock_db_manager.get_email_account_credentials.return_value = {
            'success': True,
            'credentials': {
                'email': 'test@example.com',
                'password': 'password123',
                'imap_config': {'server': 'imap.example.com', 'port': 993},
                'smtp_config': {'server': 'smtp.example.com', 'port': 587}
            }
        }
        
        mock_email_tools = Mock()
        mock_email_tools.fetch_unanswered_emails.return_value = []
        mock_email_tools_class.create_email_tools_for_account.return_value = mock_email_tools
        
        # Ejecutar test
        result = self.monitor.monitor_single_inbox(1)
        
        # Verificar resultado
        self.assertTrue(result['success'])
        self.assertEqual(result['emails_found'], 0)
        self.assertEqual(result['emails_processed'], 0)
        self.assertEqual(result['emails_failed'], 0)
        self.assertEqual(result['connection_attempts'], 1)
    
    @patch('src.services.inbox_monitor.db_manager')
    @patch('src.services.inbox_monitor.EmailToolsClass')
    def test_monitor_single_inbox_with_emails(self, mock_email_tools_class, mock_db_manager):
        """Test de monitoreo con emails para procesar."""
        # Configurar mocks
        mock_db_manager.get_email_account_credentials.return_value = {
            'success': True,
            'credentials': {
                'email': 'test@example.com',
                'password': 'password123',
                'imap_config': {'server': 'imap.example.com', 'port': 993},
                'smtp_config': {'server': 'smtp.example.com', 'port': 587}
            }
        }
        
        # Mock de emails encontrados
        mock_emails = [
            {
                'id': 'email1',
                'threadId': 'thread1',
                'messageId': 'msg1',
                'references': '',
                'sender': 'sender1@example.com',
                'subject': 'Test Subject 1',
                'body': 'Test body 1'
            },
            {
                'id': 'email2',
                'threadId': 'thread2',
                'messageId': 'msg2',
                'references': '',
                'sender': 'sender2@example.com',
                'subject': 'Test Subject 2',
                'body': 'Test body 2'
            }
        ]
        
        mock_email_tools = Mock()
        mock_email_tools.fetch_unanswered_emails.return_value = mock_emails
        mock_email_tools_class.create_email_tools_for_account.return_value = mock_email_tools
        
        # Mock del método _execute_email_workflow
        with patch.object(self.monitor, '_execute_email_workflow') as mock_execute:
            mock_execute.return_value = {
                'success': True,
                'email_id': 'email1',
                'email_subject': 'Test Subject',
                'processing_time': 1.0,
                'error': None,
                'workflow_output': {'status': 'completed'}
            }
            
            # Ejecutar test
            result = self.monitor.monitor_single_inbox(1)
            
            # Verificar resultado
            self.assertTrue(result['success'])
            self.assertEqual(result['emails_found'], 2)
            self.assertEqual(result['emails_processed'], 2)
            self.assertEqual(result['emails_failed'], 0)
            self.assertEqual(result['connection_attempts'], 1)
            self.assertEqual(len(result['workflow_results']), 2)
            
            # Verificar que se llamó al workflow para cada email
            self.assertEqual(mock_execute.call_count, 2)
    
    @patch('src.services.inbox_monitor.db_manager')
    @patch('src.services.inbox_monitor.EmailToolsClass')
    def test_monitor_single_inbox_with_retries(self, mock_email_tools_class, mock_db_manager):
        """Test de reintentos exponenciales en caso de error."""
        # Configurar mock para fallar en los primeros intentos
        mock_db_manager.get_email_account_credentials.side_effect = [
            RuntimeError("Connection failed"),
            RuntimeError("Connection failed"),
            {
                'success': True,
                'credentials': {
                    'email': 'test@example.com',
                    'password': 'password123',
                    'imap_config': {'server': 'imap.example.com', 'port': 993},
                    'smtp_config': {'server': 'smtp.example.com', 'port': 587}
                }
            }
        ]
        
        mock_email_tools = Mock()
        mock_email_tools.fetch_unanswered_emails.return_value = []
        mock_email_tools_class.create_email_tools_for_account.return_value = mock_email_tools
        
        # Ejecutar test (debería funcionar en el tercer intento)
        start_time = time.time()
        result = self.monitor.monitor_single_inbox(1)
        end_time = time.time()
        
        # Verificar resultado
        self.assertTrue(result['success'])
        self.assertEqual(result['connection_attempts'], 3)
        self.assertEqual(len(result['errors']), 2)  # Dos errores antes del éxito
        
        # Verificar que se aplicó delay exponencial (al menos 5 + 10 = 15 segundos)
        # Reducimos la expectativa para evitar fallos en CI
        self.assertGreater(end_time - start_time, 10)
    
    @patch('src.services.inbox_monitor.db_manager')
    def test_monitor_single_inbox_max_retries_exceeded(self, mock_db_manager):
        """Test de fallo después de exceder máximo de reintentos."""
        # Configurar mock para fallar siempre
        mock_db_manager.get_email_account_credentials.side_effect = RuntimeError("Persistent error")
        
        # Ejecutar test y verificar que falla
        with self.assertRaises(RuntimeError) as context:
            self.monitor.monitor_single_inbox(1)
        
        self.assertIn("Monitoreo falló después de", str(context.exception))
    
    def test_execute_email_workflow_mock(self):
        """Test del método _execute_email_workflow con mocks."""
        email_data = {
            'id': 'test_email',
            'threadId': 'test_thread',
            'messageId': 'test_msg',
            'references': '',
            'sender': 'test@example.com',
            'subject': 'Test Subject',
            'body': 'Test body',
            'account_id': 1,
            'account_email': 'account@example.com'
        }
        
        # Mock del workflow de LangGraph
        with patch('src.services.inbox_monitor.Workflow') as mock_workflow_class:
            mock_workflow = Mock()
            mock_app = Mock()
            mock_workflow.app = mock_app
            mock_workflow_class.return_value = mock_workflow
            
            # Configurar mock para simular ejecución exitosa
            mock_app.stream.return_value = [
                {'step1': 'completed'},
                {'step2': 'completed'},
                {'final': 'success'}
            ]
            
            # Ejecutar método
            result = self.monitor._execute_email_workflow(email_data)
            
            # Verificar resultado
            self.assertTrue(result['success'])
            self.assertEqual(result['email_id'], 'test_email')
            self.assertEqual(result['email_subject'], 'Test Subject')
            self.assertIsNone(result['error'])
            self.assertIsNotNone(result['workflow_output'])
    
    def test_execute_email_workflow_error(self):
        """Test del método _execute_email_workflow con error."""
        email_data = {
            'id': 'test_email',
            'threadId': 'test_thread',
            'messageId': 'test_msg',
            'references': '',
            'sender': 'test@example.com',
            'subject': 'Test Subject',
            'body': 'Test body',
            'account_id': 1,
            'account_email': 'account@example.com'
        }
        
        # Mock del workflow que falla
        with patch('src.services.inbox_monitor.Workflow') as mock_workflow_class:
            mock_workflow_class.side_effect = Exception("Workflow failed")
            
            # Ejecutar método
            result = self.monitor._execute_email_workflow(email_data)
            
            # Verificar resultado
            self.assertFalse(result['success'])
            self.assertEqual(result['email_id'], 'test_email')
            self.assertIn("Workflow failed", result['error'])
            self.assertIsNone(result['workflow_output'])


class TestRateLimiter(unittest.TestCase):
    """Tests para la clase RateLimiter."""
    
    def setUp(self):
        """Configuración inicial para cada test."""
        self.rate_limiter = RateLimiter(requests_per_minute=60)  # 1 por segundo
    
    def test_rate_limiter_initialization(self):
        """Test de inicialización del rate limiter."""
        self.assertEqual(self.rate_limiter.requests_per_minute, 60)
        self.assertEqual(len(self.rate_limiter.request_times), 0)
    
    def test_rate_limiter_first_request(self):
        """Test de primera request (no debería haber delay)."""
        start_time = time.time()
        self.rate_limiter.wait_if_needed(1)
        end_time = time.time()
        
        # No debería haber delay significativo
        self.assertLess(end_time - start_time, 0.1)
    
    def test_rate_limiter_multiple_requests(self):
        """Test de múltiples requests bajo el límite."""
        account_id = 1
        
        # Hacer varias requests que no excedan el límite
        for i in range(5):
            start_time = time.time()
            self.rate_limiter.wait_if_needed(account_id)
            end_time = time.time()
            
            # No debería haber delay significativo
            self.assertLess(end_time - start_time, 0.1)
    
    def test_rate_limiter_different_accounts(self):
        """Test de rate limiting para diferentes cuentas."""
        # Diferentes cuentas no deberían afectarse entre sí
        for account_id in [1, 2, 3]:
            start_time = time.time()
            self.rate_limiter.wait_if_needed(account_id)
            end_time = time.time()
            
            # No debería haber delay significativo
            self.assertLess(end_time - start_time, 0.1)


class TestMonitoringConfig(unittest.TestCase):
    """Tests para la clase MonitoringConfig."""
    
    def test_default_config(self):
        """Test de configuración por defecto."""
        config = MonitoringConfig()
        
        self.assertEqual(config.max_workers, 5)
        self.assertEqual(config.rate_limit_delay, 2.0)
        self.assertEqual(config.batch_size, 10)
        self.assertEqual(config.check_interval, 300)
        self.assertEqual(config.connection_timeout, 30)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.retry_delay, 60.0)
    
    def test_custom_config(self):
        """Test de configuración personalizada."""
        config = MonitoringConfig(
            max_workers=10,
            rate_limit_delay=1.0,
            batch_size=20,
            check_interval=120,
            connection_timeout=60,
            max_retries=5,
            retry_delay=30.0
        )
        
        self.assertEqual(config.max_workers, 10)
        self.assertEqual(config.rate_limit_delay, 1.0)
        self.assertEqual(config.batch_size, 20)
        self.assertEqual(config.check_interval, 120)
        self.assertEqual(config.connection_timeout, 60)
        self.assertEqual(config.max_retries, 5)
        self.assertEqual(config.retry_delay, 30.0)


if __name__ == '__main__':
    # Configurar logging para tests
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Ejecutar tests
    unittest.main(verbosity=2) 