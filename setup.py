from setuptools import setup, find_packages

setup(
    name='cilantro',
    version='0.0.1',
    description='Modular and clean blockchain by Lamden',
    author='Lamden',
    author_email='team@lamden.io',
    packages=find_packages(),
    install_requires=['pika', 'ecdsa']
)