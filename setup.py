"""Setup script for Hub Prioritization Framework"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="hub-prioritization",
    version="1.0.0",
    description="SOLID-based framework for integrated transport hub prioritization",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Hub Prioritization Team",
    python_requires=">=3.10",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "pandas>=2.0.0",
        "polars>=0.19.0",
        "numpy>=1.24.0",
        "h3>=3.7.6",
        "geopandas>=0.14.0",
        "shapely>=2.0.0",
        "pyproj>=3.6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "mypy>=1.5.0",
            "ruff>=0.1.0",
            "sphinx>=7.0.0",
            "sphinx-rtd-theme>=1.3.0",
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: GIS",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="transport hubs gis spatial-analysis solid-principles",
)
