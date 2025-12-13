import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="logpattern_converter",
    version="1.0.3",
    author="Tu Nombre Aquí",
    author_email="tu.correo@ejemplo.com",
    description="Herramienta profesional de refactorización de logs a JSON estructurado.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/echek7/logpattern_converter", 
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Environment :: Console",
    ],
    python_requires='>=3.6',
    
    install_requires=[
        'requests', 
    ],
    
    entry_points={
        'console_scripts': [
            'logconv = logpattern_converter.__main__:main',
        ],
    },
)