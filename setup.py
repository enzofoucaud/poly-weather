"""Setup script for poly-weather bot."""

from setuptools import setup, find_packages

setup(
    name="poly-weather",
    version="0.1.0",
    description="Polymarket temperature trading bot",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        # Will be read from requirements.txt
    ],
)
