Django Override Storage
=======================

Stop filling up your disk with test files or your code with file system mocks!

This project provides tools to help you reduce the side effects of using
FileFields during tests.

Simple Usage
------------

.. code-block:: python

    @locmem_override_storage
    class SimpleTestCase(TestCase):

        def test_save_file(self):
            sadf

Easy.
