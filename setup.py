# -*- coding: utf-8 -*-
from os.path import join

from hdx.utilities import CleanCommand, PackageCommand, PublishCommand
from setuptools import setup, find_packages

from hdx.utilities.loader import load_file_to_str

requirements = ['python-slugify',
                'hdx-python-api>=5.2.3']

classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "Natural Language :: English",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Programming Language :: Python :: 2.7",
    "Programming Language :: Python :: 3",
    "Topic :: Software Development :: Libraries :: Python Modules",
]

PublishCommand.version = load_file_to_str(join('src', 'hdx', 'scraper', 'geonode', 'version.txt'), strip=True)

setup(
    name='hdx-scraper-geonode',
    description='HDX Python generic geonode scraper',
    license='MIT',
    url='https://github.com/OCHA-DAP/hdx-scraper-geonode',
    version=PublishCommand.version,
    author='Michael Rans',
    author_email='rans@email.com',
    keywords=['HDX', 'scraper', 'geonode'],
    long_description=load_file_to_str('README.md'),
    long_description_content_type='text/markdown',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    include_package_data=True,
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    zip_safe=True,
    classifiers=classifiers,
    install_requires=requirements,
    cmdclass={'clean': CleanCommand, 'package': PackageCommand, 'publish': PublishCommand},
)
