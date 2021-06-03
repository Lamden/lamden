from setuptools import setup, find_packages


__version__ = '1.0.4.1'

with open("README.md", "r") as fh:
    long_desc = fh.read()


setup(
    name='lamden',
    version=__version__,
    packages=find_packages(),
    install_requires=[
        "uvloop==0.14.0",
        "sanic==20.6.3",
        "coloredlogs",
        "pymongo",
        "pyzmq",
        "requests",
        "contracting",
        "checksumdir",
        "pynacl",
        "stdlib_list",
        "lmdb"
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
