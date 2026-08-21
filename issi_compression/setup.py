from setuptools import setup, find_packages

setup(
    name="issi-compression",
    version="1.0.0",
    description="ISSI Integer String Substitution Index & Lexical Density Optimizer",
    packages=find_packages(),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "issi-demo=issi_compression.demo_issi:main"
        ]
    }
)
