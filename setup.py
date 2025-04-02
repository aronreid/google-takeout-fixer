#!/usr/bin/env python3
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="google-takeout-fixer",
    version="1.0.0",
    author="Google Takeout Fixer Contributors",
    description="A high-performance Python tool to fix metadata in Google Takeout exports",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/google-takeout-fixer",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "piexif==1.1.3",
        "tqdm==4.66.1",
        "colorama==0.4.6",
    ],
    entry_points={
        "console_scripts": [
            "google-takeout-fixer=src.main:main_cli",
        ],
    },
)
