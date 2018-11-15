from setuptools import setup, find_packages

__version__ = '0.0.1-dev'

setup(
    name='cilantro',
    version=__version__,
    packages=find_packages(exclude=['docs', 'tests']),
    install_requires=[
        'aenum==2.0.8',
        'aiodns==1.1.1',
        'aiohttp',
        'aioprocessing==1.0.1',
        'coloredlogs',
        'Cython',
        'idna==2.6',
        'mysql-connector-python',
        'ntplib==0.3.3',
        'pycapnp==0.6.3',
        '#PyNaCl==1.2.1',
        'pytest==3.5.0',
        'pytest-aiohttp==0.3.0',
        '#pyzmq==17.0.0',
        'requests==2.18.4',
        'six==1.11.0',
        'urllib3==1.22',
        'uvloop==0.9.1',
        'u-msgpack-python==2.5.0',
        'yarl==1.1.0',
        'click',
        'simple-crypt'
    ],
    dependency_links=[
        "git://github.com/Lamden/seneca.git@dev#egg=seneca"
    ],
    extras_require={
        'dev': open('dev-requirements.txt').readlines()
    },
    entry_points={
        'console_scripts': [
            'storage=cilantro.networking.storage:serve',
            'witness=cilantro.networking.witness:serve',
            'cil=cilantro.cli:main'
        ],
    },
    zip_safe=False,
    package_data={
        '': [],
        'cilantro': ['cilantro.conf'],
    },
    long_description=open('README.md').read(),
    url='https://github.com/Lamden/cilantro',
    author='Lamden',
    author_email='team@lamden.io',
    classifiers=[
        'Programming Language :: Python :: 3.6',
    ],
)
