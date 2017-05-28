from collections import defaultdict
from django.apps import apps
from django.db.models import FileField
from django.utils.functional import cached_property
from django.test.utils import TestContextDecorator

from .storage import LocMemStorage, StatsLocMemStorage


class StatsTestStorageError(Exception):
    pass


class Stats(object):

    read_cnt = 0
    save_cnt = 0

    def get_full_field_name(self, field):
        meta = field.model._meta
        return (meta.app_label, meta.model_name, field.name)

    @cached_property
    def reads_by_field(self):
        return defaultdict(list)

    @cached_property
    def saves_by_field(self):
        return defaultdict(list)

    def log_read(self, field, fname):
        self.read_cnt += 1
        self.reads_by_field[self.get_full_field_name(field)] = fname

    def log_save(self, field, fname):
        self.save_cnt += 1
        self.saves_by_field[self.get_full_field_name(field)] = fname

    def _get_content_file(self, app_label, model_name, field_name, fname):
        try:
            saved_files = self.saves_by_field[(app_label, model_name, field_name)]
        except KeyError:
            raise StatsTestStorageError(
                "{}.{}.{} has not been written to yet so there is nothing to read.".format(
                    app_label, model_name, field_name))

        if fname not in saved_files:
            raise StatsTestStorageError(
                "{}.{}.{} has not had a file named '{}' written to it. "
                "Be careful - the storage engine may have added some random "
                "characters to the name before attempting to write.".format(
                    app_label, model_name, field_name, fname))

        field = apps.get_model(app_label, model_name)._meta.get_field(field_name)
        return field.storage.open_no_log(fname)

    def get_content_file(self, field_key, fname):
        return self._get_content_file(field_key[0], field_key[1], field_key[2], fname)

    @property
    def fields_read(self):
        return list(self.reads_by_field)

    @property
    def fields_saved(self):
        return list(self.saves_by_field)


class StorageTestMixin(object):

    test_storage = None

    @cached_property
    def storage_stack(self):
        return []

    @property
    def original_storages(self):
        return self.storage_stack[0]

    previous_storages = None

    def push_storage_stack(self):
        previous_storages = self.previous_storages = {}
        self.storage_stack.append(previous_storages)
        return previous_storages

    def pop_storage_stack(self):
        popped_storages = self.storage_stack.pop()
        try:
            self.previous_storages = self.storage_stack[-1]
        except IndexError:
            self.previous_storages = None
        return popped_storages

    @cached_property
    def filefields(self):
        """
        Return list of fields which are a FileField or subclass.
        """
        filefields = []
        for model in apps.get_models():
            filefields.extend([f for f in model._meta.fields if isinstance(f, FileField)])

        return filefields

    def get_test_storage(self, field, **kwargs):
        """
        This implementation returns an instance of a storage enigne.
        """
        return self.test_storage

    def set_test_storage(self, field, **kwargs):
        if not hasattr(field, '_original_storage'):
            # Set an attribute on the field so that other StorageTestMixin
            # classes can filter on the original storage class (in a custom
            # `filefields` implementation), if they want to.
            field._original_storage = field.storage
        field.storage = self.get_test_storage(field, **kwargs)

    def setup_storage(self, **kwargs):

        previous_storages = self.push_storage_stack()
        for field in self.filefields:
            previous_storages[field] = field.storage
            self.set_test_storage(field, **kwargs)

    def teardown_storage(self):
        try:
            previous_storages = self.pop_storage_stack()
        except IndexError:
            return
        for field, original_storage in previous_storages.items():
            field.storage = original_storage


class StatsStorageTestMixin(StorageTestMixin):
    """
    Collecting the statistics requires the storage engine knowning for which
    field it is saving the file. As this the storage engine doesn't normally
    have that information, using this class requires special storage engines.
    """
    test_storage_cls = None

    def get_stats_cls(self):
        return Stats

    def get_stats_cls_kwargs(self):
        return {}

    def get_test_storage(self, field, **kwargs):
        return self.test_storage_cls(field, kwargs['stats'])

    def setup_storage(self):
        # Depending on how an instance from this class is setup, it is possible
        # that there will only be one instance for all tests (and therefore we
        # should be creating a new `stats` object in here each time). This is
        # not a concern if you use a helper fn to create a new instance each
        # time (like in `locmem_override_storage`).
        stats = self.get_stats_cls()(**self.get_stats_cls_kwargs())
        super(StatsStorageTestMixin, self).setup_storage(stats=stats)
        return stats


class StorageTestContextDecoratorBase(TestContextDecorator):
    def enable(self):
        try:
            return self.setup_storage()
        except:
            self.teardown_storage()
            raise

    def disable(self):
        self.teardown_storage()


class override_storage(StorageTestMixin, StorageTestContextDecoratorBase):

    attr_name = None
    kwarg_name = None

    def __init__(self, storage=None):
        if storage is None:
            storage = LocMemStorage()

        self.test_storage = storage


class stats_override_storage(StatsStorageTestMixin, StorageTestContextDecoratorBase):

    def __init__(self, storage_cls, kwarg_attr_name=None):

        self.attr_name = kwarg_attr_name
        self.kwarg_name = kwarg_attr_name
        self.test_storage_cls = storage_cls


def locmem_stats_override_storage(kwarg_attr_name=None):
    return stats_override_storage(StatsLocMemStorage, kwarg_attr_name)
