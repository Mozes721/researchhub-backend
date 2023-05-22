#flake8: noqa - importable modelsC
from cryptography.fernet import Fernet
from django.db import models
import secrets
import base64
from .related_models.rh_comment_model import RhCommentModel
from .related_models.rh_comment_thread_model import RhCommentThreadModel

key = Fernet.generate_key()
cipher_suite = Fernet(key)


class Encrypted(RhCommentModel):
    cipher_suite = Fernet(key)
    encryption_key = models.CharField(max_length=44)

    def encrypt(self, data):
        encrypted_data = cipher_suite.encrypt(data.encode('utf-8'))
        return encrypted_data.decode('utf-8')

    def decrypt(self, encrypted_data):
        decrypted_data = cipher_suite.decrypt(encrypted_data.encode('utf-8'))
        return decrypted_data.decode('utf-8')

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = secrets.token_hex(8)
        if not self.encryption_key:
            self.encryption_key = Fernet.generate_key().decode()

        encrypted_comment = self.encrypt(self.comment_content_json)
        self.comment_content_json = encrypted_comment
        super().save(*args, **kwargs)

    class Meta:
        abstract = True

