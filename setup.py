#!/usr/bin/env python
# -*- coding: utf-8 -*

from __future__ import absolute_import

import os
import re
from codecs import open
from setuptools import find_packages, setup

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

with open(os.path.join('libgenrs', '__init__.py'), 'r', encoding='utf-8') as init_file:
    version_match = re.search(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", init_file.read(), re.M)
    __version__ = version_match.group(1) if version_match else '0.3.0'

with open('requirements.txt') as f:
    install_requires = f.read().splitlines()

with open('README.md', 'r', encoding='utf-8') as rm_file:
    readme = rm_file.read()

setup(name='libgenrs',
      version=__version__,
      packages=find_packages(exclude=('tests',)),
      zip_safe=False,
      url='https://github.com/ramanveerji/libgenrs',
      long_description_content_type='text/markdown',
      description='Asynchronous python lib for Libgen.rs',
      download_url=f'https://github.com/ramanveerji/libgenrs/archive/v{__version__}.tar.gz',
      long_description=readme,
      license='MIT License',
      install_requires=install_requires,
      classifiers=[
          'Intended Audience :: Developers',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3.8',
          'Programming Language :: Python :: 3.9',
          'Topic :: Internet :: WWW/HTTP',
      ])
