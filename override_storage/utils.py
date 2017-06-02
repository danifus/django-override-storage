from collections import defaultdict
from inspect import isclass

from django.apps import apps
from django.db.models import FileField
from django.utils.functional import cached_property
from .compat import TestContextDecorator

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

    storage = None
    storage_cls = None
    storage_per_field = False

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

    def get_storage_cls_kwargs(self, field):
        if self.storage_cls_kwargs:
            return self.storage_cls_kwargs
        return {}

    def get_storage_from_cls(self, field):
        return self.storage_cls(**self.get_storage_cls_kwargs(field))

    def get_storage(self, field):
        """
        This implementation returns an instance of a storage enigne.
        """
        if self.storage is not None:
            return self.storage
        return self.get_storage_from_cls(field)

    def set_storage(self, field):
        if not hasattr(field, '_original_storage'):
            # Set an attribute on the field so that other StorageTestMixin
            # classes can filter on the original storage class (in a custom
            # `filefields` implementation), if they want to.
            field._original_storage = field.storage
        field.storage = self.get_storage(field)

    def setup_storage(self):

        previous_storages = self.push_storage_stack()
        for field in self.filefields:
            previous_storages[field] = field.storage
            self.set_storage(field)

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
    stats_cls = None

    def get_stats_cls_kwargs(self):
        return {}

    def _create_stats_obj(self):
        """
        Create the stats object.

        There should only be one stats object created per setUp/tearDown cycle.
        In other words, only call this method in setup_storage() and use
        get the stats object via the stats_obj attribute.
        """
        self.stats_obj = self.stats_cls(**self.get_stats_cls_kwargs())
        return self.stats_obj

    def get_stats_obj(self):
        return self.stats_obj

    def get_storage_cls_kwargs(self, field):
        kwargs = super(StatsStorageTestMixin, self).get_storage_cls_kwargs(field)
        kwargs.update({
            'stats': self.stats_obj,
            'field': field,
        })
        return kwargs

    def setup_storage(self):
        # Depending on how an instance from this class is setup, it is possible
        # that one instance will be used for all test. Creating a new `stats`
        # object on setup allows the stats to be reset between tests even if
        # this instance derived from the `StatsStorageTestMixin` persists
        # across all setup and teardowns. This is not a concern if you use a
        # helper fn to create a new `StatsStorageTestMixin` instance each
        # time (like in `locmem_stats_override_storage`).

        stats = self._create_stats_obj()
        super(StatsStorageTestMixin, self).setup_storage()
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

    def __init__(self, storage_cls_or_obj=None, storage_cls_kwargs=None,
                 storage_per_field=False):
        if storage_cls_or_obj is None:
            self.storage_cls = LocMemStorage
        else:
            if isclass(storage_cls_or_obj):
                self.storage_cls = storage_cls_or_obj
            else:
                self.storage = storage_cls_or_obj

        self.storage_cls_kwargs = storage_cls_kwargs
        self.storage_per_field = storage_per_field

    def setup_storage(self):
        if self.storage_cls is not None and not self.storage_per_field:
            self.storage = self.get_storage_from_cls(field=None)
        super(override_storage, self).setup_storage()


class stats_override_storage(StatsStorageTestMixin, StorageTestContextDecoratorBase):

    stats_cls = Stats
    attr_name = None
    kwarg_name = None

    def __init__(self, storage_cls=None, kwarg_attr_name=None,
                 storage_cls_kwargs=None):

        if storage_cls is None:
            storage_cls = StatsLocMemStorage
        self.storage_cls = storage_cls

        self.storage_cls_kwargs = storage_cls_kwargs

        if kwarg_attr_name is not None:
            self.attr_name = kwarg_attr_name
            self.kwarg_name = kwarg_attr_name


def locmem_stats_override_storage(kwarg_attr_name=None):
    return stats_override_storage(kwarg_attr_name=kwarg_attr_name)
