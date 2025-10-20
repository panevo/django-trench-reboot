from setuptools import find_packages, setup

from trench import __version__


setup(
    name="django-trench-reboot",
    version=__version__,
    packages=find_packages(exclude=("testproject", "testproject.*")),
    include_package_data=True,
    license="MIT License",
    description="REST Multi-factor authentication package for Django",
    long_description=open("README.rst").read(),
    long_description_content_type="text/x-rst",
    url="https://github.com/Panevo/django-trench-reboot",
    author="Karlo Krakan",
    author_email="karlo.krakan@panevo.com",
    install_requires=[
        "pyotp>=2.6.0",
        "twilio>=6.56.0",
        "yubico-client>=1.13.0",
        "boto3>=1.21.37",
        "smsapi-client>=2.4.5",
        "Django>=4.2.0",
        "djangorestframework>=3.10.0",
        "djangorestframework-simplejwt>=4.3.0",
    ],
    extras_require={
        "docs": [
            "sphinx >= 1.4",
            "sphinx_rtd_theme",
        ]
    },
    classifiers=[
        "Framework :: Django",
        "Framework :: Django :: 4.2",
        "Framework :: Django :: 5.0",
        "Framework :: Django :: 5.1",
        "Framework :: Django :: 5.2",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
)
