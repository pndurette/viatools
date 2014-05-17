try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

exec(open('viatools/version.py').read())

setup(
    name='viatools',
    version=__version__,
    author='Pierre Nicolas Durette',
    author_email='pndurette@gmail.com',
    url='https://github.com/pndurette/viatools',
    packages=['viatools'],
    package_data={'viatools': ['data/*', 'conf/*.conf', 'lib/*.jar']},
    license='MIT',
    description='Tools and utils to retrieve and work with VIA Rail Canada data (such as trains, stations, trips, boarding passes)',
    long_description=open('README.md').read(),
    install_requires=[
        "requests",
        "beautifulsoup4",
        "prettytable"
    ]
)
