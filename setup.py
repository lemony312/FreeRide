from setuptools import setup, find_packages

setup(
    name="freeride",
    version="1.0.0",
    description="Free AI for OpenClaw - Automatic free model management via OpenRouter",
    author="Shaishav Pidadi",
    url="https://github.com/Shaivpidadi/FreeRide",
    py_modules=["main", "watcher", "profiles"],
    install_requires=[
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "freeride=main:main",
            "freeride-watcher=watcher:main",
        ],
    },
    python_requires=">=3.8",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
)