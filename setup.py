from setuptools import setup, find_packages

__version__ = '0.0.1dev'

setup(
    name='cilantro',
    version=__version__,
    packages=find_packages(exclude=['docs', 'tests']),
    install_requires=[
        'Cython==0.29',
        'pycapnp==0.6.3',
        #PyNaCl==1.2.1
        'pyzmq==17.0.0',
        'requests==2.20.0',
        'uvloop==0.9.1',
        'u-msgpack-python==2.5.0',
        'yarl==1.1.0',
        'seneca',
        'click',
        'simple-crypt',
        'sanic',
        'pymongo==3.7.2'
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
    long_description="this is a fast blockchain",
    url='https://github.com/Lamden/cilantro',
    author='Lamden',
    author_email='team@lamden.io',
    classifiers=[
        'Programming Language :: Python :: 3.6',
    ],
)
