#flake8: noqa - importable modelsC
from cryptography.fernet import Fernet
from django.db import models
import base64
from .related_models.rh_comment_model import RhCommentModel
from .related_models.rh_comment_thread_model import RhCommentThreadModel

key = Fernet.generate_key()
encoded_key = base64.urlsafe_b64encode(key).decode('utf-8')


class EncryptedUserOrComment(models.Model):
    encrypted_comment = models.TextField()
    encrypted_username = models.TextField()

    def encrypt(self, data):
        cipher_suite = Fernet(key)
        encrypted_data = cipher_suite.encrypt(data.encode('utf-8'))
        return encrypted_data.decode('utf-8')

    def decrypt(self, encrypted_data):
        cipher_suite = Fernet(key)
        decrypted_data = cipher_suite.decrypt(encrypted_data.encode('utf-8'))
        return decrypted_data.decode('utf-8')

    def save(self, *args, **kwargs):
        self.encrypted_comment = self.encrypt(self.encrypted_comment)
        self.encrypted_username = self.encrypt(self.encrypted_username)
        super().save(*args, **kwargs)

    class Meta:
        abstract = True

