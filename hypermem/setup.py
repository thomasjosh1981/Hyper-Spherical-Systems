from setuptools import setup, find_packages

setup(
    name="hypermem",
    version="1.0.0",
    description="HyperMem Universal Context Proxy, Neuro-Phasing Engine, and M2M Tokenizer Aligner",
    author="Project Tesseract Team",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[],
    entry_points={
        "console_scripts": [
            "hypermem=hypermem.cli:main"
        ]
    }
)
