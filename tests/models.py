from django.core.files.storage import FileSystemStorage
from django.db import models


class StrictFNameFileSystemStorage(FileSystemStorage):

    def exists(self, name):
        exists = super().exists(name)
        if exists:
            raise Exception("File '{}' already exists.".format(name))
        return False


class SimpleModel(models.Model):

    upload_file = models.FileField(storage=StrictFNameFileSystemStorage())
