from setuptools import setup, find_packages

setup(
    name='auto-gpt',
    version='0.1',
    packages=['autogpt', 'auto_gpt_workspace', 'logs'],
    install_requires=[
        'torch',
        'numpy',
        'sympy',
        'networkx',
        'jinja2',
        'tqdm',
        'pyyaml',
        'scipy'
    ],
)
