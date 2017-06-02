"""
Backported from Django 1.11. These classes were introduced in 1.10 and included
here to work with older versions of Django.
"""
from functools import wraps
from unittest import TestCase

from django.utils.decorators import available_attrs


class TestContextDecorator(object):
    """
    A base class that can either be used as a context manager during tests
    or as a test function or unittest.TestCase subclass decorator to perform
    temporary alterations.
    `attr_name`: attribute assigned the return value of enable() if used as
                 a class decorator.
    `kwarg_name`: keyword argument passing the return value of enable() if
                  used as a function decorator.
    """
    def __init__(self, attr_name=None, kwarg_name=None):
        self.attr_name = attr_name
        self.kwarg_name = kwarg_name

    def enable(self):
        raise NotImplementedError

    def disable(self):
        raise NotImplementedError

    def __enter__(self):
        return self.enable()

    def __exit__(self, exc_type, exc_value, traceback):
        self.disable()

    def decorate_class(self, cls):
        if issubclass(cls, TestCase):
            decorated_setUp = cls.setUp
            decorated_tearDown = cls.tearDown

            def setUp(inner_self):
                context = self.enable()
                if self.attr_name:
                    setattr(inner_self, self.attr_name, context)
                decorated_setUp(inner_self)

            def tearDown(inner_self):
                decorated_tearDown(inner_self)
                self.disable()

            cls.setUp = setUp
            cls.tearDown = tearDown
            return cls
        raise TypeError('Can only decorate subclasses of unittest.TestCase')

    def decorate_callable(self, func):
        @wraps(func, assigned=available_attrs(func))
        def inner(*args, **kwargs):
            with self as context:
                if self.kwarg_name:
                    kwargs[self.kwarg_name] = context
                return func(*args, **kwargs)
        return inner

    def __call__(self, decorated):
        if isinstance(decorated, type):
            return self.decorate_class(decorated)
        elif callable(decorated):
            return self.decorate_callable(decorated)
        raise TypeError('Cannot decorate object of type %s' % type(decorated))
