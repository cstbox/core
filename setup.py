# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

__author__ = 'Eric Pascual - CSTB (eric.pascual@cstb.fr)'

setup(
    name='pycstbox-core',
    namespace_packages=['pycstbox'],
    author="Eric Pascual",
    author_email="eric.pascual@cstb.fr",
    description="Core part of CSTBox framework",
    url="http://cstbox.cstb.fr",
    license="LGPL",
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    packages=find_packages('lib/python'),
    package_dir={
        '': 'lib/python'
    }
)
