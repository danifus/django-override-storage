import os

HERE = os.path.dirname(__file__)

SECRET_KEY = 'fake-key'
INSTALLED_APPS = [
    'tests',
]

# Ideally nothing will be written here...
MEDIA_ROOT = os.path.join(HERE, 'media')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(HERE, 'test.db'),
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
