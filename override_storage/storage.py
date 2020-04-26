from collections import namedtuple
from threading import RLock
from urllib.parse import urljoin

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible
from django.utils.encoding import filepath_to_uri
from django.utils.functional import cached_property
from django.utils.timezone import now


FakeContent = namedtuple('FakeContent', ['content', 'time'])


@deconstructible
class LocMemStorage(Storage):

    def __init__(self, base_url=None, cache_params=None):
        self.cache = {}
        self._lock = RLock()
        self._base_url = base_url

    def _open(self, name, mode='rb'):
        if 'w' in mode:
            raise NotImplementedError("This test backend doesn't support opening a file for writing.")
        with self._lock:
            return ContentFile(self.cache.get(name).content)

    def _save(self, name, content):
        # Make sure that the cache stores the file as bytes, like it would be
        # on disk.
        content = content.read()
        if not isinstance(content, (bytes, bytearray)):
            content = content.encode()
        with self._lock:
            while name in self.cache:
                name = self.get_available_name(name)
            self.cache[name] = FakeContent(content, now())
        return name

    def _delete(self, name):
        # FileSystemStorage doesn't raise an error if the file doesn't exist.
        try:
            del self.cache[name]
        except KeyError:
            pass

    @cached_property
    def base_url(self):
        if self._base_url is not None:
            if not self._base_url.endswith('/'):
                self._base_url += '/'
            return self._base_url
        return settings.MEDIA_URL

    def path(self, name):
        """
        Return a local filesystem path where the file can be retrieved using
        Python's built-in open() function. Storage systems that can't be
        accessed using open() should *not* implement this method.
        """
        raise NotImplementedError("This backend doesn't support absolute paths.")

    def delete(self, name):
        """
        Delete the specified file from the storage system.
        """
        with self._lock:
            self._delete(name)

    def exists(self, name):
        """
        Return True if a file referenced by the given name already exists in the
        storage system, or False if the name is available for a new file.
        """
        return name in self.cache

    def listdir(self, path):
        """
        List the contents of the specified path. Return a 2-tuple of lists:
        the first item being directories, the second item being files.
        """
        raise NotImplementedError('subclasses of Storage must provide a listdir() method')

    def size(self, name):
        """
        Return the total size, in bytes, of the file specified by name.
        """
        return len(self.cache.get(name).content)

    def url(self, name):
        """
        Return an absolute URL where the file's contents can be accessed
        directly by a Web browser.
        """
        if self.base_url is None:
            raise ValueError("This file is not accessible via a URL.")
        url = filepath_to_uri(name)
        if url is not None:
            url = url.lstrip('/')
        return urljoin(self.base_url, url)

    def get_accessed_time(self, name):
        """
        Return the last accessed time (as a datetime) of the file specified by
        name. The datetime will be timezone-aware if USE_TZ=True.
        """
        return self.cache.get(name).time

    def get_created_time(self, name):
        """
        Return the creation time (as a datetime) of the file specified by name.
        The datetime will be timezone-aware if USE_TZ=True.
        """
        return self.cache.get(name).time

    def get_modified_time(self, name):
        """
        Return the last modified time (as a datetime) of the file specified by
        name. The datetime will be timezone-aware if USE_TZ=True.
        """
        return self.cache.get(name).time


class StatsLocMemStorage(LocMemStorage):
    def __init__(self, field, stats, cache_params=None):
        self.stats = stats
        self.field = field
        super(StatsLocMemStorage, self).__init__(cache_params)

    def log_read(self, name):
        self.stats.log_read(self.field, name)

    def log_save(self, name):
        self.stats.log_save(self.field, name)

    def _open(self, name,  mode='rb'):
        self.log_read(name)
        return super(StatsLocMemStorage, self)._open(name, mode)

    def open_no_log(self, name,  mode='rb'):
        return super(StatsLocMemStorage, self)._open(name, mode)

    def _save(self, name, content):
        self.log_save(name)
        return super(StatsLocMemStorage, self)._save(name, content)

    def log_delete(self, name):
        self.stats.log_delete(self.field, name)

    def _delete(self, name):
        self.log_delete(name)
        return super(StatsLocMemStorage, self)._delete(name)
