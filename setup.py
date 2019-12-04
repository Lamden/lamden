from setuptools import setup, find_packages
from setuptools.command.install import install


__version__ = '0.0.3'

with open("README.md", "r") as fh:
    long_desc = fh.read()


class PostInstallCommand(install):
    """ Triggers post installation boot script to startup node"""
    def run(self):
        # boot script here
        install.run(self)

setup(
    name='cilantro_ee',
    version=__version__,
    packages=find_packages(exclude=['docs', 'ops', 'docker', 'deprecated']),
    install_requires=[
        'Cython==0.29',
        'pycapnp==0.6.3',
        #PyNaCl==1.2.1
        'pyzmq==17.0.0',
        'requests==2.20.0',
        'uvloop==0.9.1',
        'u-msgpack-python==2.5.0',
        'yarl==1.1.0',
        'contracting',
        'click',
        'simple-crypt',
        'sanic==19.6.3',
        'pymongo==3.7.2'
        'rocks'
    ],
    extras_require={
        'dev': open('dev-requirements.txt').readlines()
    },
    entry_points={
        'console_scripts': [
            'cilantro_ee=__main__:main'
        ],
    },
    zip_safe=False,
    package_data={
        '': [],
        'cilantro_ee': ['cilantro_ee.conf'],
    },
    cmdclass ={
      'install': PostInstallCommand,
    },
    description = "Lamden Blockchain",
    long_description= long_desc,
    long_description_content_type="text/markdown",
    url='https://github.com/Lamden/cilantro-enterprise',
    author='Lamden',
    author_email='team@lamden.io',
    classifiers=[
        'Programming Language :: Python :: 3.6',
    ],
    python_requires='>=3.6.5',
)
