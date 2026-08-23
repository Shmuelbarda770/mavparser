"""Build configuration for the CPython extension module."""

import sys
from setuptools import Extension, setup

if sys.platform == "win32":
    extra_compile_args = ["/O2", "/W3"]
else:
    extra_compile_args = ["-O3", "-Wall", "-Wextra"]

setup(
    ext_modules=[
        Extension(
            "mavparser._mavparser",
            sources=["mavparser/parser.c"],
            extra_compile_args=extra_compile_args,
        )
    ]
)