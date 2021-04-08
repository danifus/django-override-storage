import os

from django.core.files.base import ContentFile
from django.test import TestCase
from django.test.utils import override_settings

from .models import SimpleModel, SimpleProxyModel
from .context import override_storage

try:
    from unittest import mock
except ImportError:
    import mock


original_storage = SimpleModel._meta.get_field('upload_file').storage


@override_storage.override_storage()
class OverrideStorageClassNoAttrTestCase(TestCase):

    def save_file(self, name, content):
        expected_path = original_storage.path(name)
        obj = SimpleModel()
        obj.upload_file.save(name, ContentFile(content))
        return expected_path

    def test_class_decorator(self):
        expected_path = self.save_file('class_decorator.txt', 'class_decorator')
        self.assertFalse(os.path.exists(expected_path))


class OverrideStorageTestCase(TestCase):

    def save_file(self, name, content):
        expected_path = original_storage.path(name)
        obj = SimpleModel()
        obj.upload_file.save(name, ContentFile(content))
        return expected_path

    def test_context_manager(self):
        with override_storage.override_storage(storage=override_storage.LocMemStorage()):
            expected_path = self.save_file('test_context_mngr.txt', 'context_mngr')
        self.assertFalse(os.path.exists(expected_path))

    def test_specified_storage(self):
        storage = override_storage.LocMemStorage()
        upload_file_field = SimpleModel._meta.get_field('upload_file')
        original_storage = upload_file_field.storage
        with override_storage.override_storage(storage=storage):
            self.assertEqual(upload_file_field.storage, storage)
        self.assertEqual(upload_file_field.storage, original_storage)

    def test_file_saved(self):
        name = 'saved_file.txt'
        content = 'saved_file'.encode()
        obj = SimpleModel()
        with override_storage.override_storage():
            obj.upload_file.save(name, ContentFile(content))
            read_content = obj.upload_file.read()
        expected_path = original_storage.path(name)

        self.assertFalse(os.path.exists(expected_path))
        self.assertEqual(content, read_content)

    def test_save_bytes_data(self):
        """save works with bytes objects with bytes which can't be decoded to
        ascii in both Python 2 and 3.
        """
        name = 'saved_file.txt'
        content = b'saved_file \xff'
        obj = SimpleModel()
        with override_storage.override_storage():
            obj.upload_file.save(name, ContentFile(content))
            read_content = obj.upload_file.read()
        expected_path = original_storage.path(name)

        self.assertFalse(os.path.exists(expected_path))
        self.assertEqual(content, read_content)

    @override_settings(MEDIA_URL="/media/")
    def test_default_url(self):
        name = 'saved_file.txt'
        content = 'saved_file'.encode()
        obj = SimpleModel()
        with override_storage.override_storage():
            obj.upload_file.save(name, ContentFile(content))
            url = obj.upload_file.url

        self.assertEqual(url, "/media/" + name)

    def test_base_url(self):
        name = 'saved_file.txt'
        content = 'saved_file'.encode()
        obj = SimpleModel()
        with override_storage.override_storage(storage_kwargs={"base_url": "/my_media/"}):
            obj.upload_file.save(name, ContentFile(content))
            url = obj.upload_file.url
        self.assertEqual(url, "/my_media/" + name)

    def test_method_decorator_with_no_parens_raises_error(self):
        """Using override_storage fails as a decorator with no parens."""
        with self.assertRaises(override_storage.TestStorageError):
            @override_storage.override_storage
            def fake_fn():
                pass

    @override_storage.override_storage()
    def test_method_decorator_no_kwarg(self):
        expected_path = self.save_file('test_method_decorator.txt', 'method_decorator')
        self.assertFalse(os.path.exists(expected_path))

    def test_nested_overrides(self):
        upload_file_field = SimpleModel._meta.get_field('upload_file')
        original_storage = upload_file_field.storage
        outer_storage = override_storage.LocMemStorage()
        inner_storage = override_storage.LocMemStorage()
        with override_storage.override_storage(storage=outer_storage):
            self.assertEqual(upload_file_field.storage, outer_storage)

            with override_storage.override_storage(storage=inner_storage):
                self.assertEqual(upload_file_field.storage, inner_storage)

            self.assertEqual(upload_file_field.storage, outer_storage)
        self.assertEqual(upload_file_field.storage, original_storage)

    def test_proxy_models(self):
        """Proxy models should not interfer with the override or tear down.

        Because proxy models have the same filefield instance as the parent
        model, there is a risk that a filefield storage will be overridden
        twice affecting the ability to restore it to its original storage.
        """
        # Make sure that the tests actually have a proxy model present.
        self.assertTrue(SimpleProxyModel._meta.proxy)
        upload_file_field = SimpleModel._meta.get_field('upload_file')
        original_storage = upload_file_field.storage
        with override_storage.override_storage():
            self.assertNotEqual(upload_file_field.storage, original_storage)
        self.assertEqual(upload_file_field.storage, original_storage)

    def test_delete(self):
        """delete removes entry from cache."""
        storage = override_storage.LocMemStorage()
        name = 'test_file'
        content = ContentFile('test')
        storage._save(name, content)

        self.assertTrue(name in storage.cache)
        storage.delete(name)
        self.assertFalse(name in storage.cache)

    def test_delete_missing_key(self):
        """delete asserts no error if the key is already not in the cache."""
        storage = override_storage.LocMemStorage()
        name = 'test_file'
        self.assertFalse(name in storage.cache)
        storage.delete(name)


class StatsOverrideStorageTestCase(TestCase):

    def save_file(self, name, content):
        expected_path = original_storage.path(name)
        obj = SimpleModel()
        obj.upload_file.save(name, ContentFile(content))
        return expected_path

    def test_context_manager(self):
        with override_storage.locmem_stats_override_storage():
            expected_path = self.save_file('test_context_mngr.txt', 'context_mngr')
        self.assertFalse(os.path.exists(expected_path))

    @override_storage.locmem_stats_override_storage(name='override_storage_field')
    def test_method_decorator(self, override_storage_field):
        self.assertEqual(override_storage_field.save_cnt, 0)
        expected_path = self.save_file('test_method_decorator.txt', 'method_decorator')
        self.assertFalse(os.path.exists(expected_path))
        self.assertEqual(override_storage_field.save_cnt, 1)

    @override_storage.locmem_stats_override_storage()
    def test_method_decorator_no_kwarg(self):
        expected_path = self.save_file('test_method_decorator.txt', 'method_decorator')
        self.assertFalse(os.path.exists(expected_path))

    def test_method_decorator_with_no_parens_raises_error(self):
        """Using locmem_stats_override_storage fails as a decorator with no parens."""
        with self.assertRaises(override_storage.TestStorageError):
            @override_storage.locmem_stats_override_storage
            def fake_fn():
                pass

    def test_nested_overrides(self):

        upload_file_field = SimpleModel._meta.get_field('upload_file')
        original_storage = upload_file_field.storage
        with override_storage.locmem_stats_override_storage() as storage1:
            nested_1_storage = upload_file_field.storage
            self.assertNotEqual(original_storage, nested_1_storage)
            self.assertEqual(storage1.save_cnt, 0)
            self.save_file('save_outer_1', 'save_outer_1')
            self.save_file('save_outer_2', 'save_outer_2')
            self.assertEqual(storage1.save_cnt, 2)
            with override_storage.locmem_stats_override_storage() as storage2:
                nested_2_storage = upload_file_field.storage
                self.assertNotEqual(nested_1_storage, nested_2_storage)
                self.assertEqual(storage1.save_cnt, 2)
                self.assertEqual(storage2.save_cnt, 0)
                self.save_file('save_inner_1', 'save_inner_1')
                self.assertEqual(storage2.save_cnt, 1)
                self.assertEqual(storage1.save_cnt, 2)

            self.assertEqual(upload_file_field.storage, nested_1_storage)
        self.assertEqual(upload_file_field.storage, original_storage)

    def test_read_and_save_cnt(self):

        with override_storage.locmem_stats_override_storage() as storage:
            name = 'file.txt'
            content = 'file content'.encode()
            self.assertEqual(storage.read_cnt, 0)
            self.assertEqual(storage.save_cnt, 0)

            obj = SimpleModel()
            obj.upload_file.save(name, ContentFile(content))

            self.assertEqual(storage.save_cnt, 1)
            self.assertEqual(storage.read_cnt, 0)

            read_content = obj.upload_file.read()

            self.assertEqual(storage.read_cnt, 1)
            self.assertEqual(content, read_content)

    def test_get_file_contents(self):
        with override_storage.locmem_stats_override_storage() as storage:
            name = 'file.txt'
            content = 'file content'.encode()

            self.assertEqual(storage.read_cnt, 0)

            obj = SimpleModel()
            obj.upload_file.save(name, ContentFile(content))

            field_key, name_key = list(storage.saves_by_field.items())[0]
            read_content = storage.get_content_file(field_key, name_key)
            self.assertEqual(content, read_content.read())

            # make sure accessing via stats doesn't increment the stats.
            self.assertEqual(storage.read_cnt, 0)

    def test_get_file_contents_not_written(self):
        fname = 'wrong_test.txt'
        upload_file_field = SimpleModel._meta.get_field('upload_file')
        with override_storage.locmem_stats_override_storage() as storage:
            field_key = storage.get_full_field_name(upload_file_field)
            with self.assertRaises(override_storage.StatsTestStorageError):
                storage.get_content_file(field_key, fname)

            obj = SimpleModel()
            obj.upload_file.save('test.txt', ContentFile('content'))
            with self.assertRaises(override_storage.StatsTestStorageError):
                storage.get_content_file(field_key, fname)

    def test_delete(self):
        """delete removes entry from cache."""
        # TODO: initialise a StatsLocMemStorage
        with override_storage.locmem_stats_override_storage() as stats:
            name = 'test_file'
            obj = SimpleModel()
            obj.upload_file.save(name, ContentFile('content'))
            obj.upload_file.delete()
            self.assertEqual(stats.delete_cnt, 1)

    def test_delete_missing_key(self):
        """delete asserts no error if the key is already not in the cache.

        Still adds to the delete count.
        """
        with override_storage.locmem_stats_override_storage() as stats:
            name = 'test_file'
            obj = SimpleModel()
            obj.upload_file.save(name, ContentFile('content'))
            obj.upload_file.delete()
            self.assertEqual(stats.delete_cnt, 1)
            obj.upload_file.delete()
            self.assertEqual(stats.delete_cnt, 1)


@override_storage.locmem_stats_override_storage(name='override_storage_field')
class StatsOverrideStorageClassTestCase(TestCase):

    override_storage_field = None

    def save_file(self, name, content):
        expected_path = original_storage.path(name)
        obj = SimpleModel()
        obj.upload_file.save(name, ContentFile(content))
        return expected_path

    def test_class_decorator(self):
        expected_path = self.save_file('class_decorator.txt', 'class_decorator')
        self.assertFalse(os.path.exists(expected_path))

    def test_class_decorator_attr_name(self):
        self.assertEqual(self.override_storage_field.save_cnt, 0)
        self.save_file('class_decorator.txt', 'class_decorator')
        self.assertEqual(self.override_storage_field.save_cnt, 1)


@override_storage.locmem_stats_override_storage()
class StatsOverrideStorageClassNoAttrTestCase(TestCase):

    def save_file(self, name, content):
        expected_path = original_storage.path(name)
        obj = SimpleModel()
        obj.upload_file.save(name, ContentFile(content))
        return expected_path

    def test_class_decorator(self):
        expected_path = self.save_file('class_decorator.txt', 'class_decorator')
        self.assertFalse(os.path.exists(expected_path))


class TearDownTestCase(TestCase):
    def test_teardown(self):
        class WeirdError(Exception):
            pass
        with mock.patch('override_storage.override_storage.setup_storage', side_effect=WeirdError()):
            with self.assertRaises(WeirdError):
                # Make sure it raises the real error and does the tear down
                # without failing.
                with override_storage.override_storage():
                    pass


@override_storage.override_storage()
class NoPersistenceTestCase(TestCase):

    def assertNoRecords(self):
        test_storage = SimpleModel._meta.get_field('upload_file').storage
        self.assertEqual(len(test_storage.cache), 0)

    def test_persistence_1(self):
        self.assertNoRecords()
        obj = SimpleModel()
        obj.upload_file.save('test_1', ContentFile('content'))

    def test_persistence_2(self):
        self.assertNoRecords()
        obj = SimpleModel()
        obj.upload_file.save('test_2', ContentFile('content'))
