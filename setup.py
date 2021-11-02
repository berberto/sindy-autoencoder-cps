from setuptools import setup

setup(name='sindy_autoencoder_cps',
    version='0.0.1',
    description='PyTorch implementation of SINDy auto-encoders',
    author='Henrik Steude',
    dependencies=[
        'pytorch',
        'pysindy',
        'pytorch-lightning',
        'typing_extensions',
        'pyarrow',
        'fastparquet',
        ]
)
