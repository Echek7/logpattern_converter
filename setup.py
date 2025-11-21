from setuptools import setup, find_packages

setup(
    name='logpattern-converter',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        # No se requieren dependencias externas para la lógica básica
    ],
    entry_points={
        'console_scripts': [
            'logconv=logconv:main',
        ],
    },
    author='Echek7 (AGI_ECHE)',
    author_email='contact@agi-eche.com',
    description='Herramienta CLI para la conversión y refactorización de patrones de logs.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/Echek7/logpattern_converter',
    license='Proprietary (Licencia de Pago Único)',
)
