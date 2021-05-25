import warnings
from collections import defaultdict

from django.apps import apps
from django.db.models import FileField
from django.utils.functional import cached_property
from django.test.utils import TestContextDecorator

from .storage import LocMemStorage, StatsLocMemStorage


class TestStorageError(Exception):
    pass


class StatsTestStorageError(Exception):
    pass


class Stats(object):

    read_cnt = 0
    save_cnt = 0
    delete_cnt = 0

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

    def log_delete(self, field, fname):
        self.delete_cnt += 1
        self.deletes_by_field[self.get_full_field_name(field)] = fname

    @cached_property
    def deletes_by_field(self):
        return defaultdict(list)

    @property
    def fields_delete(self):
        return list(self.deletes_by_field)

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
    storage_callable = None
    storage_per_field = False

    @cached_property
    def storage_stack(self):
        return []

    @property
    def original_storages(self):
        return self.storage_stack[0]

    previous_storages = None

    def push_storage_stack(self):
        self.previous_storages = {}
        self.storage_stack.append(self.previous_storages)
        return self.previous_storages

    def pop_storage_stack(self):
        popped_storages = self.storage_stack.pop()
        try:
            self.previous_storages = self.storage_stack[-1]
        except IndexError:
            self.previous_storages = None
        return popped_storages

    def get_field_hash(self, field):
        # GH#8:
        # In Django < 3.2, instances of fields that appear on multiple
        # models via inheritance do not have unique hashes from __hash__
        # for each model they eventually appear on. This causes the
        # dictionary value in previous_storages to be overwritten when
        # the same field is used on multiple models via inheritance as
        # __hash__ is the same.
        # This hash value implementation is taken from django 3.2
        return hash((
            field.creation_counter,
            field.model._meta.app_label if hasattr(field, 'model') else None,
            field.model._meta.model_name if hasattr(field, 'model') else None,
        ))

    @cached_property
    def filefields(self):
        """
        Return list of fields which are a FileField or subclass.
        """
        filefields = []
        for model in apps.get_models():
            filefields.extend([f for f in model._meta.fields if isinstance(f, FileField)])

        return filefields

    def get_storage_kwargs(self, field):
        if self.storage_kwargs:
            return self.storage_kwargs
        return {}

    def get_storage_from_callable(self, field):
        return self.storage_callable(**self.get_storage_kwargs(field))

    def get_storage(self, field):
        """
        This implementation returns an instance of a storage enigne.
        """
        if self.storage is not None:
            return self.storage
        return self.get_storage_from_callable(field)

    def set_storage(self, field):
        if not hasattr(field, '_original_storage'):
            # Set an attribute on the field so that other StorageTestMixin
            # classes can filter on the original storage class (in a custom
            # `filefields` implementation), if they want to.
            field._original_storage = field.storage
        field.storage = self.get_storage(field)

    def setup_storage(self):
        """Save existing FileField storages and patch them with test instance(s)."""

        previous_storages = self.push_storage_stack()
        for field in self.filefields:
            if self.get_field_hash(field) in previous_storages:
                # Proxy models share field instances across multiple objects
                # but we only want to replace their storage once. Replacing
                # the storage multiple times results in losing track of what
                # the original storage was previously and breaks restoring the
                # field to its original storage.
                continue
            previous_storages[self.get_field_hash(field)] = (
                field, field.storage
            )
            self.set_storage(field)

    def teardown_storage(self):
        try:
            previous_storages = self.pop_storage_stack()
        except IndexError:
            return
        for field, original_storage in previous_storages.values():
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

    def get_storage_kwargs(self, field):
        kwargs = super(StatsStorageTestMixin, self).get_storage_kwargs(field)
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
    def __init__(self, unused_arg=None, **kwargs):
        """Inits class with check for correct calling patterns.

        Subclasses should also declare unused_arg as their first argument.
        This defends against passing the function to be wrapped as the first
        arg to this init method rather than as the first argument to the
        resulting instance, which does act like a decorator.

        Failing to do this can result in undesired behaviour, such as not
        executing the wrapped function at all.

        eg.
        - Proper usage with parenthesis on the decorator:
            @subclass()
            def wrapped_fn():
                pass

        - Incorrect usage without parenthesis. Exception will be raised:
            @subclass
            def wrapped_fn():
                pass
        """
        if unused_arg is not None:
            raise TestStorageError(
                'Incorrect usage: Positional arguments, calling as a decorator '
                'without parenthesis and specifying the `unused_arg` keyword '
                'are not supported.')

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

    def __init__(self, unused_arg=None, storage=None,
                 storage_kwargs=None, storage_per_field=False,
                 storage_cls_or_obj=None, storage_cls_kwargs=None):
        """Return an object to override the storage engines of FileFields.

        Instance can be used as a decorator or context manager.

        Args:
            unused_arg: If anything apart from None, an error will be raised.
                Defends against accidental misuse as a decorator.
            storage (optional): storage instance or callable that returns a
                storage instance. LocMemStorage by default.
            storage_kwargs (optional): kwargs passed to storage if storage is
                callable.
            storage_per_field (optional): When storage is callable, if False
                (default), use one result from the callable to replace all
                FileField fields. If True and storage is callable, replace
                every FileField with a different call to the storage callable.
        """
        super(override_storage, self).__init__(unused_arg)

        if storage_cls_or_obj is not None:
            warnings.warn(
                'storage_cls_or_obj is deprecated. Use storage instead.',
                DeprecationWarning)
            if storage is not None:
                raise TestStorageError(
                    'storage_cls_or_obj is deprecated and was specified with '
                    'as well as storage. Only use storage.')
            storage = storage_cls_or_obj

        if storage_cls_kwargs is not None:
            warnings.warn(
                'storage_cls_kwargs is deprecated. Use storage_kwargs instead.',
                DeprecationWarning)
            if storage_kwargs is not None:
                raise TestStorageError(
                    'storage_cls_kwargs is deprecated and was specified with '
                    'as well as storage_kwargs. Only use storage_kwargs.')
            storage_kwargs = storage_cls_kwargs

        if storage is None:
            self.storage_callable = LocMemStorage
        else:
            if hasattr(storage, '__call__'):
                self.storage_callable = storage
            else:
                self.storage = storage

        self.storage_kwargs = storage_kwargs
        self.storage_per_field = storage_per_field

    def setup_storage(self):
        """Save existing FileField storages and patch them with test instance(s).

        If storage_per_field is False (default) this function will create a
        single instance here and assign it to self.storage to be used for all
        filefields.
        If storage_per_field is True, an independent storage instance will be
        used for each FileField .
        """
        if self.storage_callable is not None and not self.storage_per_field:
            self.storage = self.get_storage_from_callable(field=None)
        super(override_storage, self).setup_storage()


class stats_override_storage(StatsStorageTestMixin, StorageTestContextDecoratorBase):

    stats_cls = Stats
    attr_name = None
    kwarg_name = None

    def __init__(self, unused_arg=None, storage=None, storage_kwargs=None,
                 name=None):

        super(stats_override_storage, self).__init__(unused_arg)

        if storage is None:
            self.storage_callable = StatsLocMemStorage
        else:
            self.storage_callable = storage

        self.storage_kwargs = storage_kwargs

        if name is not None:
            self.attr_name = name
            self.kwarg_name = name


def locmem_stats_override_storage(unused_arg=None, name=None):
    return stats_override_storage(unused_arg, name=name)
