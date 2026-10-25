#===--errors.py------------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Exception hierarchy shared by all automation scripts."""

from __future__ import annotations


class AutomationError(Exception):
    """Base exception for automation failures that should exit with a non-zero status."""


class ConfigurationError(AutomationError):
    """Raised when configuration is missing or invalid."""


class AuthenticationError(AutomationError):
    """Raised when authentication cannot be resolved safely."""


class GitCommandError(AutomationError, RuntimeError):
    """Raised when a Git command fails."""


class MergeConflictError(AutomationError):
    """Raised when histories cannot be merged without manual resolution."""
