# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


with open('README.rst') as f:
    readme = f.read()

#with open('LICENSE') as f:
#    license = f.read()

setup(
    name='proxytools',
    version='0.0.1',
    description='Search and test public web proxies',
    long_description=readme,
    author='Luke Maxwell',
    author_email='luke@codepunk.xyz',
    url='',
    #license=license,
    packages=['proxytools'],
    entry_points = {
        'console_scripts': ['proxytools=proxytools.cli:cli'],
    },
    install_requires=[
        'backports-abc>=0.4',
        'click>=6.6',
        'lxml>=3.6.0',
        'pycurl>=7.43.0',
        'tornado>=4.3',
        'colorama>=0.3.7',
    ],
    # packages=find_packages(exclude=('tests', 'docs'))
)

