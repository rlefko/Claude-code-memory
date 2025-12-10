"""CLI package for UI consistency guard.

This package provides the command-line interface for running UI consistency
checks, including the pre-commit guard and reporters for different output formats.
"""

from .guard import UIGuard
from .reporter import CLIReporter, JSONReporter

__all__ = ["UIGuard", "CLIReporter", "JSONReporter"]
