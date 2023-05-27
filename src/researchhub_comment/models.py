#flake8: noqa - importable modelsC
from .related_models.rh_comment_model import RhCommentModel
from .related_models.rh_comment_thread_model import RhCommentThreadModel

from cryptography.fernet import Fernet
from django.db import models



key = Fernet.generate_key()
cipher_suite = Fernet(key)


class EncryptUser(models.Model):
    cipher_suite = Fernet(key)
    encryption_key = models.CharField(max_length=44)

    def encrypt(self, data):
        encrypted_data = cipher_suite.encrypt(data.encode('utf-8'))
        return encrypted_data.decode('utf-8')

    def decrypt(self, encrypted_data):
        decrypted_data = cipher_suite.decrypt(encrypted_data.encode('utf-8'))
        return decrypted_data.decode('utf-8')

