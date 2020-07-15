from setuptools import setup, find_packages


__version__ = '1.0'

with open("README.md", "r") as fh:
    long_desc = fh.read()


setup(
    name='cilantro',
    version=__version__,
    packages=find_packages(),

    # Note install requirements have to be same as dev-requirement.txt (for aws)
    install_requires=[
        "sanic",
        "coloredlogs",
        "pymongo",
        "pyzmq",
        "requests",
        "contracting",
        "checksumdir",
        "pynacl"
    ],
    entry_points={
        'console_scripts': [
            'cil=cilantro.cli.cmd:main'
        ],
    },
    zip_safe=False,
    package_data={
        '': [],
        'cilantro': ['cilantro.conf'],
    },
    description="Lamden Blockchain",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    url='https://github.com/Lamden/cilantro-enterprise',
    author='Lamden',
    author_email='team@lamden.io',
    classifiers=[
        'Programming Language :: Python :: 3.6',
    ],
    python_requires='>=3.6.5',
)
