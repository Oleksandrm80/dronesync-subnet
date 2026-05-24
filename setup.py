from setuptools import setup, find_packages

setup(
    name="dronesync-subnet",
    version="0.1.0",
    description="Konnex subnet for urban drone swarm coordination",
    author="Oleksandr Malchev",
    author_email="malchevoleksandr@gmail.com",
    url="https://github.com/Oleksandrm80/dronesync-subnet",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "pyyaml>=6.0",
        "requests>=2.31.0",
        "websockets>=11.0",
        "python-dotenv>=1.0.0",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
    ],
)