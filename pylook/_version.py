# Copyright (c) 2020 Leeman Geophysical LLC.
# Distributed under the terms of the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause
"""Tools for versioning."""


def get_version():
    """Get the package version.

    Either get it from package metadata, or get it using version control information if
    a development install.
    """
    try:
        from setuptools_scm import get_version
        return get_version(root='..', relative_to=__file__,
                           version_scheme='post-release', local_scheme='dirty-tag')
    except (ImportError, LookupError):
        from pkg_resources import get_distribution
        return get_distribution(__package__).version
