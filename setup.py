import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="FMLC",
    version="1.0.0",
    author="Gehbauer, Christoph",
    description="A framework/backend for multi-layer and multi-time domain controller.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/LBNL-ETA/FMLC",
    project_urls={
        "Bug Tracker": "https://github.com/LBNL-ETA/FMLC/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    packages=setuptools.find_packages(),
    python_requires=">=3.6",
    install_requires= ['pandas']
)