from setuptools import setup, find_packages

__version__ = '0.0.1-dev'

setup(
    name='cilantro',
    version=__version__,
    packages=find_packages(exclude=['docs', 'tests']),
    install_requires=open('requirements.txt').readlines(),
    extras_require={
        'dev': open('dev-requirements.txt').readlines()
    },
    entry_points={
        'console_scripts': [
            'storage=cilantro.networking.storage:serve',
            'witness=cilantro.networking.witness:serve'
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
    email='team@lamden.io',
    classifiers=[
        'Programming Language :: Python :: 3.6',
    ],
)
