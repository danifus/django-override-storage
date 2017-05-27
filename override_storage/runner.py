from django.test.runner import DiscoverRunner

from .storage import LocMemStorage
from .utils import StorageTestMixin


class StorageRunnerMixin(StorageTestMixin):

    def setup_test_environment(self):
        super().setup_test_environment()
        self.setup_storage()

    def teardown_test_environment(self):
        super().teardown_test_environment()
        self.teardown_storage()


class LocMemStorageDiscoverRunner(StorageRunnerMixin, DiscoverRunner):

    test_storage_cls = LocMemStorage
