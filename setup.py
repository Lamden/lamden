from setuptools import setup, find_packages

__version__ = '0.0.1-dev'

setup(
    name='cilantro',
    version=__version__,
    packages=find_packages(exclude=['docs', 'tests']),
    install_requires=[
        'aiodns==1.1.1',
        'aiohttp==2.3.9',
        'async-timeout==2.0.0',
        'cchardet==2.1.1',
        'certifi==2018.1.18',
        'chardet==3.0.4',
        'idna==2.6',
        'multidict==4.1.0',
        'pycares==2.3.0',
        'pyzmq==16.0.4',
        'requests==2.18.4',
        'twofish==0.3.0',
        'urllib3==1.22',
        'uvloop==0.9.1',
        'yarl==1.1.0',
        'zmq==0.0.0',
    ],
    zip_safe=False,
    package_data={
        '': [],
        'cilantro': ['cilantro.conf'],
    },
    long_description=open('README.md').read(),
    url='https://github.com/Lamden/cilantro',
    author='Lamden',
    email='developers@lamden.io',
    classifiers=[
        'Programming Language :: Python :: 3.6',
    ],
)
