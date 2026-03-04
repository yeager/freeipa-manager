from setuptools import setup, find_packages
setup(
    name="freeipa-manager",
    version="0.2.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "freeipa-manager=freeipa_manager.cli.commands:main",
        ],
    },
)
