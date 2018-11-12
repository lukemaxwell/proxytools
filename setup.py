# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='proxytools',
    version='0.0.1',
    description='Search and test public web proxies',
    long_description=readme,
    author='Luke Maxwell',
    author_email='luke@codepunk.xyz',
    url='https://github.com/lukemaxwell/proxytools',
    license=license,
    packages=['proxytools'],
    entry_points = {
        'console_scripts': ['proxytools=proxytools.cli:cli'],
    },
    install_requires=[
        'asyncio',
        'beautifulsoup4', # required for pandas.read_html
        'click',
        'html5lib', # required for pandas.read_html
        'inscriptis',
        'lxml',
        'pandas',
        'pyppeteer',
        'requests',
        'yarl',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    # packages=find_packages(exclude=('tests', 'docs'))
)

