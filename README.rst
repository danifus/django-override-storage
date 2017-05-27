Django Override Storage
=======================

Stop filling up your disk with test files or your code with file system mocks!

This project provides tools to help you reduce the side effects of using
FileFields during tests.

Simple Usage
------------

``locmem_override_storage`` patches all ``FileField`` fields to store the
contents of the file in an in-memory cache and returns them to their previous
storages when leaving its context.

It can be used similarly to ``django.test.utils.override_settings``: as a class
decorator, a method decorator or a context manager.


.. code-block:: python

    import os

    from django.core.files.base import ContentFile
    from django.test import TestCase

    import override_storage

    from .models import SimpleModel

    class OverrideStorageTestCase(TestCase):

        def save_file(self, name, content):
            expected_path = original_storage.path(name)
            obj = SimpleModel()
            obj.upload_file.save(name, ContentFile(content))
            return expected_path

        def test_context_manager(self):
            with override_storage.locmem_override_storage:
                expected_path = self.save_file('test_context_mngr.txt', 'context_mngr')
            self.assertFalse(os.path.exists(expected_path))

        @override_storage.locmem_override_storage
        def test_method_decorator(self):
            expected_path = self.save_file('test_method_decorator.txt', 'method_decorator')
            self.assertFalse(os.path.exists(expected_path))


    @override_storage.locmem_override_storage
    class OverrideStorageClassTestCase(TestCase):
        def save_file(self, name, content):
            expected_path = original_storage.path(name)
            obj = SimpleModel()
            obj.upload_file.save(name, ContentFile(content))
            return expected_path

        def test_class_decorator(self):
            expected_path = self.save_file('class_decorator.txt', 'class_decorator')
            self.assertFalse(os.path.exists(expected_path))


It can also be used globally through a custom test runner. This can be acheived
by setting the ``TEST_RUNNER`` setting in your settings file or however else
you may choose to define the django test runner.

.. code-block:: python

    TEST_RUNNER = 'override_storage.LocMemStorageDiscoverRunner'


Easy.
