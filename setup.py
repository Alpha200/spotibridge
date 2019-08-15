from setuptools import find_packages, setup

setup(
    name='spotilight',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'paho-mqtt',
        'apscheduler',
        'git+https://github.com/plamere/spotipy.git',
    ],
)
