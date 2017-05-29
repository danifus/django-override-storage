import os
import mock

from django.core.files.base import ContentFile
from django.test import TestCase

from .models import SimpleModel
from .context import override_storage
from .context import storage


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
        with override_storage.override_storage(override_storage.LocMemStorage()):
            expected_path = self.save_file('test_context_mngr.txt', 'context_mngr')
        self.assertFalse(os.path.exists(expected_path))

    def test_specified_storage(self):
        storage = override_storage.LocMemStorage()
        upload_file_field = SimpleModel._meta.get_field('upload_file')
        original_storage = upload_file_field.storage
        with override_storage.override_storage(storage):
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

    @override_storage.override_storage()
    def test_method_decorator_no_kwarg(self):
        expected_path = self.save_file('test_method_decorator.txt', 'method_decorator')
        self.assertFalse(os.path.exists(expected_path))

    def test_nested_overrides(self):
        upload_file_field = SimpleModel._meta.get_field('upload_file')
        original_storage = upload_file_field.storage
        outer_storage = override_storage.LocMemStorage()
        inner_storage = override_storage.LocMemStorage()
        with override_storage.override_storage(outer_storage):
            self.assertEqual(upload_file_field.storage, outer_storage)

            with override_storage.override_storage(inner_storage):
                self.assertEqual(upload_file_field.storage, inner_storage)

            self.assertEqual(upload_file_field.storage, outer_storage)
        self.assertEqual(upload_file_field.storage, original_storage)


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

    @override_storage.locmem_stats_override_storage('override_storage')
    def test_method_decorator(self, override_storage):
        self.assertEqual(override_storage.save_cnt, 0)
        expected_path = self.save_file('test_method_decorator.txt', 'method_decorator')
        self.assertFalse(os.path.exists(expected_path))
        self.assertEqual(override_storage.save_cnt, 1)

    @override_storage.locmem_stats_override_storage()
    def test_method_decorator_no_kwarg(self):
        expected_path = self.save_file('test_method_decorator.txt', 'method_decorator')
        self.assertFalse(os.path.exists(expected_path))

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


@override_storage.locmem_stats_override_storage('override_storage')
class StatsOverrideStorageClassTestCase(TestCase):

    override_storage = None

    def save_file(self, name, content):
        expected_path = original_storage.path(name)
        obj = SimpleModel()
        obj.upload_file.save(name, ContentFile(content))
        return expected_path

    def test_class_decorator(self):
        expected_path = self.save_file('class_decorator.txt', 'class_decorator')
        self.assertFalse(os.path.exists(expected_path))

    def test_class_decorator_attr_name(self):
        self.assertEqual(self.override_storage.save_cnt, 0)
        self.save_file('class_decorator.txt', 'class_decorator')
        self.assertEqual(self.override_storage.save_cnt, 1)


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
        self.assertEqual(len(test_storage.cache._cache), 0)

    def test_persistence_1(self):
        self.assertNoRecords()
        obj = SimpleModel()
        obj.upload_file.save('test_1', ContentFile('content'))

    def test_persistence_2(self):
        self.assertNoRecords()
        obj = SimpleModel()
        obj.upload_file.save('test_2', ContentFile('content'))


@override_storage.override_storage()
class NoCullTestCase(TestCase):

    def test_no_cull(self):
        cache = storage.PrivateLocMemCache()
        for i in range(cache._max_entries + 1):
            cache.add(i, i)

        cache._cull()
        self.assertEqual(len(cache._cache), cache._max_entries + 1)
