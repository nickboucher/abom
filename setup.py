import setuptools

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name='abom-clang',
    version='0.1',
    author='Nicholas Boucher',
    author_email='nicholas.boucher@cl.cam.ac.uk',
    description='Automatic Bill of Materials for clang',
    keywords='abom, bom, clang',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/nickboucher/abom-clang',
    package_dir={'': 'abom-clang'},
    packages=setuptools.find_packages(where='abom-clang'),
    python_requires='>=3.6',
    install_requires=[
            'bloom_filter2',
            'termcolor'
        ],
    entry_points={
        'console_scripts': [
            'abom=compile:compile',
            'abom-check=check:check'
        ],
    },
)