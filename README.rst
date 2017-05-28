Django Override Storage
=======================

Stop filling up your disk with test files or your code with file system mocks!

This project provides tools to help you reduce the side effects of using
FileFields during tests.


Simple Usage
------------
``override_storage`` patches all ``FileField`` fields to store the contents of
the file in an in-memory cache and returns the fields to their previous
storages when leaving its context.

It can be used similarly to ``django.test.utils.override_settings``: as a class
decorator, a method decorator or a context manager.

.. code-block:: python

    from django.core.files.base import ContentFile
    from django.test import TestCase

    from override_storage import override_storage
    from override_storage.storage import LocMemStorage

    from .models import SimpleModel

    class OverrideStorageTestCase(TestCase):

        def test_context_manager(self):
            with override_storage():
                # By default, all files saved to in memory cache.
                obj = SimpleModel()
                obj.upload_file.save('test.txt', ContentFile('content'))

                # Get your file back!
                content = obj.upload_file.read()

        @override_storage(LocMemStorage())
        def test_method_decorator(self):
            # You can also specify to replace all storage backends with a
            # storage instance of your choosing.
            ...

        @override_storage()
        def test_method_decorator(self):
            # Used as a method decorator.
            ...


    @override_storage()
    class OverrideStorageClassTestCase(TestCase):
        # You can also wrap classes.
        ...


It can also be used globally through a custom test runner. This can be achieved
by setting the ``TEST_RUNNER`` setting in your settings file or however else
you may choose to define the Django test runner.

.. code-block:: python

    TEST_RUNNER = 'override_storage.LocMemStorageDiscoverRunner'

Modifying the test runner does not modify the testcase classes which are run.
This means that the cache is not reset between tests as it is for the
decorators or context manager. Use these other options if you expect the files
written for the test suite to consume a lot of memory.


Storage information
-------------------

Like ``override_storage``, ``locmem_stats_override_storage`` patches all
``FileField`` fields to store the contents of the file in an in-memory cache
and returns the fields to their previous storages when leaving its context.

In addition to the normal functionality, it returns an object with information
about the calls to the ``_open`` and ``_save`` methods of the test storage. In
general it records which fields have had files read from or written to them and
the names of the files are recorded.

.. code-block:: python

    from django.core.files.base import ContentFile
    from django.test import TestCase

    from override_storage import locmem_stats_override_storage

    from .models import SimpleModel

    class OverrideStorageTestCase(TestCase):

        def test_context_manager(self):
            with locmem_stats_override_storage() as storage_stats:
                # All files saved to in memory cache.
                obj = SimpleModel()
                obj.upload_file.save('test.txt', ContentFile('content'))

                # Check how many files have been saved
                self.storage_stats.save_cnt

                # Check which fields were read or saved
                self.storage_stats.fields_saved
                self.storage_stats.fields_read

                # Get a list of names, by field, which have been saved or
                # read.
                self.storage_stats.reads_by_field
                self.storage_stats.saves_by_field

                # Get your file back!
                content = obj.upload_file.read()

        @locmem_stats_override_storage('storage_stats')
        def test_method_decorator(self, storage_stats):
            # access to storage stats by specifying kwarg
            ...


    @locmem_stats_override_storage('storage_stats')
    class OverrideStorageClassTestCase(TestCase):
        storage_stats = None

        # access to storage stats by specifying attr_name
        ...
