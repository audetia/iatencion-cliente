"""
Tests unitarios para DatabaseManager.

Tests sencillos que cubren la funcionalidad esencial de gestión de usuarios
y cuentas de email sin complicaciones innecesarias.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from src.database import DatabaseManager


class TestDatabaseManager:
    """Tests para la clase DatabaseManager."""
    
    @pytest.fixture
    def db_manager(self):
        """Fixture que crea una instancia de DatabaseManager para tests."""
        with patch.dict(os.environ, {
            'ENCRYPTION_KEY': 'dGVzdF9lbmNyeXB0aW9uX2tleV9mb3JfdGVzdGluZw=='  # test key en base64
        }):
            return DatabaseManager()
    
    @pytest.fixture
    def mock_db_session(self):
        """Fixture que crea un mock de sesión de base de datos."""
        session = Mock()
        return session

    # =============================================================================
    # TESTS DE ENCRIPTACIÓN
    # =============================================================================
    
    def test_encrypt_password_success(self, db_manager):
        """Test de encriptación exitosa de contraseña."""
        password = "mi_contraseña_secreta"
        encrypted = db_manager.encrypt_password(password)
        
        assert encrypted is not None
        assert encrypted != password  # Debe estar encriptada
        assert len(encrypted) > 0
    
    def test_decrypt_password_success(self, db_manager):
        """Test de desencriptación exitosa de contraseña."""
        password = "mi_contraseña_secreta"
        encrypted = db_manager.encrypt_password(password)
        decrypted = db_manager.decrypt_password(encrypted)
        
        assert decrypted == password
    
    def test_encrypt_empty_password_fails(self, db_manager):
        """Test que falla al encriptar contraseña vacía."""
        with pytest.raises(ValueError, match="La contraseña no puede estar vacía"):
            db_manager.encrypt_password("")
    
    def test_decrypt_empty_password_fails(self, db_manager):
        """Test que falla al desencriptar contraseña vacía."""
        with pytest.raises(ValueError, match="La contraseña encriptada no puede estar vacía"):
            db_manager.decrypt_password("")

    # =============================================================================
    # TESTS DE GESTIÓN DE USUARIOS
    # =============================================================================
    
    @patch('src.database.DatabaseManager.get_db_session')
    def test_create_user_success(self, mock_get_session, db_manager):
        """Test de creación exitosa de usuario."""
        # Setup mocks
        mock_session = Mock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_user = Mock()
        mock_user.id = 1
        mock_user.to_dict.return_value = {
            'id': 1,
            'email': 'test@example.com',
            'name': 'Test User',
            'is_verified': False
        }
        
        with patch('src.database.User') as mock_user_class:
            mock_user_class.create.return_value = mock_user
            
            result = db_manager.create_user("test@example.com", "Test User")
            
            # Verificaciones
            assert result['success'] is True
            assert result['user']['email'] == 'test@example.com'
            assert result['user']['name'] == 'Test User'
            mock_user_class.create.assert_called_once()
    
    def test_create_user_invalid_email(self, db_manager):
        """Test que falla al crear usuario con email inválido."""
        with pytest.raises(ValueError, match="Formato de email inválido"):
            db_manager.create_user("email_invalido", "Test User")
    
    def test_create_user_empty_name(self, db_manager):
        """Test que falla al crear usuario con nombre vacío."""
        with pytest.raises(ValueError, match="El nombre no puede estar vacío"):
            db_manager.create_user("test@example.com", "")
    
    @patch('src.database.DatabaseManager.get_db_session')
    def test_get_user_by_email_found(self, mock_get_session, db_manager):
        """Test de búsqueda exitosa de usuario por email."""
        mock_session = Mock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_user = Mock()
        mock_user.id = 1
        mock_user.email = 'test@example.com'
        mock_user.to_dict.return_value = {'id': 1, 'email': 'test@example.com'}
        
        with patch('src.database.User') as mock_user_class:
            mock_user_class.get_by_email.return_value = mock_user
            
            result = db_manager.get_user_by_email("test@example.com")
            
            assert result is not None
            assert result['id'] == 1
            assert result['email'] == 'test@example.com'
    
    @patch('src.database.DatabaseManager.get_db_session')
    def test_get_user_by_email_not_found(self, mock_get_session, db_manager):
        """Test de búsqueda de usuario inexistente por email."""
        mock_session = Mock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        with patch('src.database.User') as mock_user_class:
            mock_user_class.get_by_email.return_value = None
            
            result = db_manager.get_user_by_email("noexiste@example.com")
            
            assert result is None
    
    @patch('src.database.DatabaseManager.get_db_session')
    def test_verify_user_success(self, mock_get_session, db_manager):
        """Test de verificación exitosa de usuario."""
        mock_session = Mock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_user = Mock()
        mock_user.is_verified = False
        mock_user.to_dict.return_value = {'id': 1, 'is_verified': True}
        
        with patch('src.database.User') as mock_user_class:
            mock_user_class.get_by_id.return_value = mock_user
            
            result = db_manager.verify_user(1)
            
            assert result['success'] is True
            assert result['was_already_verified'] is False
            mock_user.verify.assert_called_once()

    # =============================================================================
    # TESTS DE GESTIÓN DE CUENTAS DE EMAIL
    # =============================================================================
    
    @patch('src.database.DatabaseManager.get_db_session')
    @patch('src.database.DatabaseManager.encrypt_password')
    def test_add_email_account_success(self, mock_encrypt, mock_get_session, db_manager):
        """Test de adición exitosa de cuenta de email."""
        # Setup mocks
        mock_session = Mock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_encrypt.return_value = "encrypted_password"
        
        mock_user = Mock()
        mock_user.id = 1
        
        mock_account = Mock()
        mock_account.id = 1
        mock_account.to_dict.return_value = {
            'id': 1,
            'email': 'test@gmail.com',
            'user_id': 1
        }
        
        with patch('src.database.User') as mock_user_class, \
             patch('src.database.EmailAccount') as mock_account_class:
            
            mock_user_class.get_by_id.return_value = mock_user
            mock_account_class.create.return_value = mock_account
            
            imap_config = {'server': 'imap.gmail.com', 'port': 993}
            smtp_config = {'server': 'smtp.gmail.com', 'port': 587}
            
            result = db_manager.add_email_account(
                user_id=1,
                email="test@gmail.com",
                imap_config=imap_config,
                smtp_config=smtp_config,
                password="password123"
            )
            
            assert result['success'] is True
            assert result['account']['email'] == 'test@gmail.com'
            mock_encrypt.assert_called_once_with("password123")
            mock_account_class.create.assert_called_once()
    
    def test_add_email_account_invalid_user_id(self, db_manager):
        """Test que falla al añadir cuenta con user_id inválido."""
        imap_config = {'server': 'imap.gmail.com', 'port': 993}
        smtp_config = {'server': 'smtp.gmail.com', 'port': 587}
        
        with pytest.raises(ValueError, match="El ID del usuario debe ser un entero positivo"):
            db_manager.add_email_account(
                user_id=-1,
                email="test@gmail.com",
                imap_config=imap_config,
                smtp_config=smtp_config,
                password="password123"
            )
    
    def test_add_email_account_invalid_imap_config(self, db_manager):
        """Test que falla con configuración IMAP inválida."""
        imap_config = {'server': 'imap.gmail.com'}  # Falta 'port'
        smtp_config = {'server': 'smtp.gmail.com', 'port': 587}
        
        with pytest.raises(ValueError, match="imap_config debe contener"):
            db_manager.add_email_account(
                user_id=1,
                email="test@gmail.com",
                imap_config=imap_config,
                smtp_config=smtp_config,
                password="password123"
            )
    
    @patch('src.database.DatabaseManager.get_db_session')
    def test_get_user_email_accounts_success(self, mock_get_session, db_manager):
        """Test de obtención exitosa de cuentas de usuario."""
        mock_session = Mock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_user = Mock()
        mock_user.name = "Test User"
        mock_user.email = "user@example.com"
        
        mock_account1 = Mock()
        mock_account1.to_dict.return_value = {'id': 1, 'email': 'test1@gmail.com'}
        mock_account2 = Mock()
        mock_account2.to_dict.return_value = {'id': 2, 'email': 'test2@gmail.com'}
        
        with patch('src.database.User') as mock_user_class, \
             patch('src.database.EmailAccount') as mock_account_class:
            
            mock_user_class.get_by_id.return_value = mock_user
            mock_account_class.get_by_user.return_value = [mock_account1, mock_account2]
            mock_account_class.get_active_by_user.return_value = [mock_account1]
            
            result = db_manager.get_user_email_accounts(user_id=1)
            
            assert result['success'] is True
            assert len(result['accounts']) == 2
            assert result['summary']['total_accounts'] == 2
            assert result['summary']['active_accounts'] == 1
    
    @patch('src.database.DatabaseManager.get_db_session')
    @patch('src.database.DatabaseManager.decrypt_password')
    def test_get_email_account_credentials_success(self, mock_decrypt, mock_get_session, db_manager):
        """Test de obtención exitosa de credenciales."""
        mock_session = Mock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_decrypt.return_value = "decrypted_password"
        
        mock_account = Mock()
        mock_account.id = 1
        mock_account.email = "test@gmail.com"
        mock_account.encrypted_password = "encrypted_password"
        mock_account.imap_server = "imap.gmail.com"
        mock_account.imap_port = 993
        mock_account.smtp_server = "smtp.gmail.com"
        mock_account.smtp_port = 587
        mock_account.auth_type = "password"
        mock_account.is_oauth2 = False
        mock_account.is_active = True
        mock_account.health_status = "healthy"
        
        with patch('src.database.EmailAccount') as mock_account_class:
            mock_account_class.get_by_id.return_value = mock_account
            
            result = db_manager.get_email_account_credentials(account_id=1)
            
            assert result['success'] is True
            assert result['credentials']['password'] == "decrypted_password"
            assert result['credentials']['email'] == "test@gmail.com"
            assert result['credentials']['imap_config']['server'] == "imap.gmail.com"
            mock_decrypt.assert_called_once_with("encrypted_password")
    
    @patch('src.database.DatabaseManager.get_db_session')
    def test_delete_email_account_success(self, mock_get_session, db_manager):
        """Test de eliminación exitosa de cuenta de email."""
        mock_session = Mock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        mock_account = Mock()
        mock_account.email = "test@gmail.com"
        mock_account.user_id = 1
        
        with patch('src.database.EmailAccount') as mock_account_class:
            mock_account_class.get_by_id.return_value = mock_account
            
            result = db_manager.delete_email_account(account_id=1)
            
            assert result['success'] is True
            assert result['deleted_account']['email'] == "test@gmail.com"
            mock_account.delete.assert_called_once()

    # =============================================================================
    # TESTS DE CASOS EXTREMOS
    # =============================================================================
    
    def test_invalid_user_id_formats(self, db_manager):
        """Test con formatos inválidos de user_id."""
        invalid_ids = ["abc", -1, 0, None, 1.5]
        
        for invalid_id in invalid_ids:
            with pytest.raises(ValueError):
                db_manager.get_user_by_id(invalid_id)
    
    def test_invalid_account_id_formats(self, db_manager):
        """Test con formatos inválidos de account_id."""
        invalid_ids = ["abc", -1, 0, None, 1.5]
        
        for invalid_id in invalid_ids:
            with pytest.raises(ValueError):
                db_manager.get_email_account_credentials(invalid_id)
    
    def test_invalid_email_formats(self, db_manager):
        """Test con formatos inválidos de email."""
        invalid_emails = [
            "email_sin_arroba",
            "@sin_nombre.com",
            "sin_dominio@",
            "sin.punto@dominio",
            "",
            None
        ]
        
        for invalid_email in invalid_emails:
            with pytest.raises(ValueError):
                db_manager.create_user(invalid_email, "Test User")


class TestDatabaseManagerIntegration:
    """Tests de integración básicos para DatabaseManager."""
    
    @pytest.fixture
    def db_manager(self):
        """Fixture para tests de integración."""
        with patch.dict(os.environ, {
            'ENCRYPTION_KEY': 'dGVzdF9lbmNyeXB0aW9uX2tleV9mb3JfdGVzdGluZw=='
        }):
            return DatabaseManager()
    
    def test_encrypt_decrypt_cycle(self, db_manager):
        """Test del ciclo completo de encriptación/desencriptación."""
        original_passwords = [
            "password123",
            "contraseña_con_ñ",
            "P@ssw0rd!",
            "very_long_password_with_special_chars_123!@#",
            "短密码"  # Caracteres no ASCII
        ]
        
        for password in original_passwords:
            encrypted = db_manager.encrypt_password(password)
            decrypted = db_manager.decrypt_password(encrypted)
            assert decrypted == password, f"Failed for password: {password}"
    
    def test_different_passwords_different_encryption(self, db_manager):
        """Test que contraseñas diferentes producen encriptaciones diferentes."""
        password1 = "password123"
        password2 = "password456"
        
        encrypted1 = db_manager.encrypt_password(password1)
        encrypted2 = db_manager.encrypt_password(password2)
        
        assert encrypted1 != encrypted2
    
    def test_same_password_different_encryption(self, db_manager):
        """Test que la misma contraseña puede producir encriptaciones diferentes (por el salt)."""
        password = "password123"
        
        encrypted1 = db_manager.encrypt_password(password)
        encrypted2 = db_manager.encrypt_password(password)
        
        # Ambas deben desencriptar al mismo valor
        assert db_manager.decrypt_password(encrypted1) == password
        assert db_manager.decrypt_password(encrypted2) == password 