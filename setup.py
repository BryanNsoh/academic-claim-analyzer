# setup.py
import subprocess
import sys
from setuptools import setup, find_packages
from setuptools.command.develop import develop
from setuptools.command.install import install

class PostInstallCommand(install):
    def run(self):
        install.run(self)
        self.install_playwright_browsers()

    def install_playwright_browsers(self):
        subprocess.check_call([sys.executable, "-m", "playwright", "install"])

class PostDevelopCommand(develop):
    def run(self):
        develop.run(self)
        self.install_playwright_browsers()

    def install_playwright_browsers(self):
        subprocess.check_call([sys.executable, "-m", "playwright", "install"])

with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='academic-claim-analyzer',
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    author='Bryan Nsoh',
    author_email='bryan.anye.5@gmail.com',
    description='A tool for analyzing academic claims',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/BryanNsoh/async_llm_handler',
    packages=find_packages(),
    install_requires=[
        'aiohttp',
        'anthropic',
        'google-generativeai',
        'openai',
        'python-dotenv',
        'tiktoken',
        'asyncio',
        'beautifulsoup4',
        'PyMuPDF',
        'playwright==1.36.0',
        'fake-useragent',
        'async-llm-handler'
    ],
    extras_require={
        'dev': ['pytest', 'pytest-asyncio'],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
    cmdclass={
        'develop': PostDevelopCommand,
        'install': PostInstallCommand,
    },
)