from django.core.files.storage import FileSystemStorage
from django.db import models


class StrictFNameFileSystemStorage(FileSystemStorage):

    def exists(self, name):
        exists = super(StrictFNameFileSystemStorage, self).exists(name)
        if exists:
            raise Exception("File '{}' already exists.".format(name))
        return False


class SimpleModel(models.Model):

    upload_file = models.FileField(storage=StrictFNameFileSystemStorage())


class SimpleProxyModel(SimpleModel):
    """Proxy models share the same field instance as the parent model. This
    model ensures the tear down process restores the field to the original
    state even if a particular field instance is seen multiple times.
    """

    class Meta:
        proxy = True
