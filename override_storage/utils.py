from django.apps import apps
from django.db.models import FileField
from django.utils.functional import cached_property
from django.test.utils import TestContextDecorator

from .storage import LocMemStorage


class StorageTestMixin:

    test_storage_cls = None

    @cached_property
    def original_storages(self):
        return {}

    @cached_property
    def filefields(self):
        """
        Return list of fields which are a FileField or subclass.
        """
        filefields = []
        for model in apps.get_models():
            filefields.extend([f for f in model._meta.fields if isinstance(f, FileField)])

        return filefields

    def get_test_storage(self):
        return self.test_storage_cls()

    def set_test_storage(self, field):
        field.storage = self.get_test_storage()

    def setup_storage(self):
        for field in self.filefields:
            self.original_storages[field] = field.storage
            self.set_test_storage(field)

    def teardown_storage(self):
        for field, original_storage in self.original_storages.items():
            field.storage = original_storage


class override_storage(StorageTestMixin, TestContextDecorator):

    def __init__(self, storage_cls, attr_name=None, kwarg_name=None):
        self.test_storage_cls = storage_cls
        super().__init__(attr_name=attr_name, kwarg_name=kwarg_name)

    def enable(self):
        try:
            self.setup_storage()
        except:
            self.teardown_storage()
            raise

    def disable(self):
        self.teardown_storage()


locmem_override_storage = override_storage(LocMemStorage)
