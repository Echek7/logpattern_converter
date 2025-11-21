from setuptools import setup, find_packages

setup(
    name='logpattern-converter',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'click',
    ],
    entry_points={
        'console_scripts': [
            'logconv = logpattern_converter:cli',
        ],
    },
    # ¡CORRECCIÓN! Usamos una URL válida para pasar la validación de PyPI.
    author='LogPattern Converter AGI',
    description='Herramienta de Arbitraje de Código para la refactorización rápida de patrones de logs.',
    long_description='Convierte formatos de log legacy (ej. Splunk/Logstash) a formatos modernos (ej. OpenTelemetry) usando inferencia de patrones impulsada por AGI. Ahorra cientos de horas de ingeniería.',
    url='https://github.com/Eche/logpattern-converter-agi', # URL de ejemplo válida
    license='Proprietary (License Key Required for Full Functionality)',
)
