"""Build configuration for the CPython extension module."""

from setuptools import Extension, setup


setup(
    ext_modules=[
        Extension(
            "mavparser._mavparser",
            sources=["mavparser/parser.c"],
            extra_compile_args=["-O3", "-Wall", "-Wextra"],
        )
    ]
)