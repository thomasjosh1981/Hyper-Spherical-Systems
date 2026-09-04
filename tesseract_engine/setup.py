from setuptools import setup, find_packages

setup(
    name="tesseract-engine",
    version="1.0.0",
    description="Tesseract 3D Center-Out Tensor, 5+1 DLASC Cipher & 5-File Chameleon Stripe Vault",
    packages=find_packages(),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "tesseract-vault=tesseract_engine.demo_stripe_vault:run_demo"
        ]
    }
)
