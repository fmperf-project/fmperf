from distutils.core import setup

setup(
    name="fmperf",
    version="0.0.1",
    package_data={"fmperf.data": ["ai.txt"]},
    packages=["fmperf", "fmperf.utils", "fmperf.loadgen", "fmperf.data"],
)
