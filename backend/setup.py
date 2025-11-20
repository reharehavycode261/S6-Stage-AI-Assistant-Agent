#!/usr/bin/env python3
"""
Configuration setup.py pour le projet AI-Agent.
"""

from setuptools import setup, find_packages
import os

# Lire le README s'il existe
long_description = ""
if os.path.exists("README.md"):
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()

# Lire les requirements
requirements = []
if os.path.exists("requirements.txt"):
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        requirements = [line.strip() for line in fh.readlines() if line.strip() and not line.startswith("#")]

setup(
    name="ai-agent",
    version="1.0.0",
    author="Smartelia",
    author_email="contact@smartelia.fr",
    description="Agent d'Automatisation IA avec LangGraph et Monday.com",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/smartelia/ai-agent",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "test": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-mock>=3.10.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "ai-agent=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.yml", "*.yaml", "*.json"],
    },
    project_urls={
        "Bug Reports": "https://github.com/smartelia/ai-agent/issues",
        "Source": "https://github.com/smartelia/ai-agent",
        "Documentation": "https://docs.smartelia.fr/ai-agent",
    },
) 