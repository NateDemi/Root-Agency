from setuptools import setup, find_packages

setup(
    name="retail-agency",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'agency-swarm<1.0.0',
        'langchain',
        'langchain-openai',
        'pandas',
        'python-dotenv',
    ],
    python_requires='>=3.9',
) 