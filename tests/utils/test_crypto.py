"""
Tests for encryption utilities.
"""
import pytest
from cryptography.fernet import Fernet

from app.utils.crypto import encrypt, decrypt, EncryptionService


class TestEncryption:
    """Test encryption and decryption functions."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encryption and decryption should return original value."""
        plaintext = "test_password_123"
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)

        assert decrypted == plaintext
        assert encrypted != plaintext

    def test_encrypt_returns_different_output(self):
        """Encrypted text should be different from plaintext."""
        plaintext = "sensitive_data"
        encrypted = encrypt(plaintext)

        assert encrypted != plaintext
        assert len(encrypted) > len(plaintext)

    def test_encrypt_empty_string(self):
        """Empty string should encrypt and decrypt correctly."""
        encrypted = encrypt("")
        decrypted = decrypt("")

        assert encrypted == ""
        assert decrypted == ""

    def test_decrypt_invalid_data_raises_error(self):
        """Decrypting invalid data should raise an error."""
        with pytest.raises(Exception):
            decrypt("invalid_encrypted_data")

    def test_encrypt_unicode_characters(self):
        """Should handle unicode characters correctly."""
        plaintext = "password_with_émojis_🔒"
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)

        assert decrypted == plaintext

    def test_encryption_service_instance(self):
        """EncryptionService should work as instance."""
        service = EncryptionService()
        plaintext = "test_data"

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_long_string_encryption(self):
        """Should handle long strings correctly."""
        plaintext = "a" * 10000
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)

        assert decrypted == plaintext
        assert len(decrypted) == 10000

    def test_special_characters(self):
        """Should handle special characters in password."""
        plaintext = "p@ssw0rd!#$%^&*(){}[]<>?/|\\:;"
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)

        assert decrypted == plaintext
