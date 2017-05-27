# -*- coding: utf-8 -*-

from setuptools import setup, find_packages


with open('README.rst') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='override_storage',
    version='0.1.0',
    description='Django test helpers to manage file storage side effects.',
    long_description=readme,
    author='Daniel Hillier',
    author_email='daniel.hillier@gmail.com',
    url='https://github.com/danifus/django_override_storage',
    license=license,
    packages=find_packages(exclude=('tests', 'docs'))
)
