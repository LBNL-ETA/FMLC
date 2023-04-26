import setuptools

# description
with open('README.md', 'r', encoding='utf8') as f:
    long_description = f.read()

# requirements
with open('requirements.txt', 'r', encoding='utf8') as f:
    install_requires = f.read().splitlines()

# version
with open('fmlc/__init__.py', 'r', encoding='utf8') as f:
    version = json.loads(f.read().split('__version__ = ')[1].split('\n')[0])

setuptools.setup(
    name="FMLC",
    version=version,
    author="Gehbauer, Christoph",
    description="A framework/backend for multi-layer and multi-time domain controller.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license_files = ['license.txt'],
    url="https://github.com/LBNL-ETA/FMLC",
    project_urls={
        "Bug Tracker": "https://github.com/LBNL-ETA/FMLC/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    packages=['fmlc'],
    python_requires=">=3.6",
    install_requires= install_requires
)