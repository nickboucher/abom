import setuptools

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name='abom',
    version='0.1',
    author='Nicholas Boucher',
    author_email='nicholas.boucher@cl.cam.ac.uk',
    description='Automatic Bill of Materials',
    keywords='abom, bom, clang',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/nickboucher/abom',
    package_dir={'': 'src'},
    packages=setuptools.find_packages(where='src'),
    python_requires='>=3.6',
    install_requires=[
            'termcolor',
            'bitarray',
            'yaecl@git+https://github.com/nickboucher/YAECL-Yet-Another-Entropy-Coding-Library.git',
            'tqdm',
            'matplotlib',
            'numpy'
        ],
    entry_points={
        'console_scripts': [
            'abom=build:build',
            'abom-check=check:check',
            'abom-tuning=utils.tuning:main'
        ],
    },
)