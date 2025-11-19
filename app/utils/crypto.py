"""
Encryption utilities for securing sensitive data like Garmin credentials.
"""
from cryptography.fernet import Fernet
from app.config import settings


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""

    def __init__(self):
        """Initialize with encryption key from settings."""
        self.cipher = Fernet(settings.ENCRYPTION_KEY.encode())

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: String to encrypt

        Returns:
            Encrypted string (base64 encoded)
        """
        if not plaintext:
            return ""
        encrypted_bytes = self.cipher.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            encrypted_text: Encrypted string (base64 encoded)

        Returns:
            Decrypted plaintext string
        """
        if not encrypted_text:
            return ""
        decrypted_bytes = self.cipher.decrypt(encrypted_text.encode())
        return decrypted_bytes.decode()


# Global encryption service instance
encryption_service = EncryptionService()


def encrypt(plaintext: str) -> str:
    """Convenience function to encrypt a string."""
    return encryption_service.encrypt(plaintext)


def decrypt(encrypted_text: str) -> str:
    """Convenience function to decrypt a string."""
    return encryption_service.decrypt(encrypted_text)
