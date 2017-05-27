import os

from django.core.files.base import ContentFile
from django.test import TestCase

from .models import SimpleModel
from .context import override_storage


original_storage = SimpleModel._meta.get_field('upload_file').storage


class OverrideStorageTestCase(TestCase):

    def save_file(self, name, content):
        expected_path = original_storage.path(name)
        obj = SimpleModel()
        obj.upload_file.save(name, ContentFile(content))
        return expected_path

    def test_context_manager(self):
        with override_storage.locmem_override_storages:
            expected_path = self.save_file('test_context_mngr.txt', 'context_mngr')
        self.assertFalse(os.path.exists(expected_path))

    @override_storage.locmem_override_storages
    def test_method_decorator(self):
        expected_path = self.save_file('test_method_decorator.txt', 'method_decorator')
        self.assertFalse(os.path.exists(expected_path))


@override_storage.locmem_override_storages
class OverrideStorageClassTestCase(TestCase):
    def save_file(self, name, content):
        expected_path = original_storage.path(name)
        obj = SimpleModel()
        obj.upload_file.save(name, ContentFile(content))
        return expected_path

    def test_class_decorator(self):
        expected_path = self.save_file('class_decorator.txt', 'class_decorator')
        self.assertFalse(os.path.exists(expected_path))
