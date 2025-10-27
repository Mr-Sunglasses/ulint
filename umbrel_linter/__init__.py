"""
Umbrel Linter - A Python linter for Umbrel app stores and applications.

This package provides comprehensive linting capabilities for Umbrel applications,
including YAML validation, Docker Compose validation, and directory structure checks.
"""

__version__ = "0.1.0"
__author__ = "Umbrel Team"
__email__ = "linter@umbrel.com"

from .core.linter import UmbrelLinter
from .core.models import LintingError, LintingResult, Severity

__all__ = [
    "LintingError",
    "LintingResult",
    "Severity",
    "UmbrelLinter",
]
