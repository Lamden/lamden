from setuptools import setup, find_packages


__version__ = '2.0.18.0'

with open("README.md", "r") as fh:
    long_desc = fh.read()


setup(
    name='lamden',
    version=__version__,
    packages=find_packages(),
    install_requires=[
        "chardet==3.0.4",
        "ujson==1.35",  # locking dep for websockets
        "idna==2.10",  # locking dep for sanic
        "typing_extensions==3.10.0.0",  # locking dep for pyzmq
        "bidict==0.21.4",  # locking deb for socketio
        "multidict==4.7.6", # locking dep for sanic
        "yarl==1.4.2", # locking dep for python-socketio
        "uvloop==0.14.0",
        "aiofiles==22.1.0",
        "sanic==20.6.3",
        "coloredlogs==15.0.1",
        "pyzmq==23.1.0",
        "requests==2.25.1",
        "checksumdir==1.2.0",
        "pynacl==1.5.0",
        "stdlib_list==0.8.0",
        "psutil==5.9.1",
        "python-socketio==5.5.2",
        "aiohttp==3.8.1",
        "iso8601"
    ],
    entry_points={
        'console_scripts': [
            'lamden=lamden.cli.cmd:main'
        ],
    },
    zip_safe=False,
    description="Lamden Blockchain",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    url='https://github.com/Lamden/lamden',
    author='Lamden',
    author_email='team@lamden.io',
    classifiers=[
        'Programming Language :: Python :: 3.6',
    ],
    python_requires='>=3.6.5',
    package_data={
        "": ["*.json"]
    }
)
