#===--sanitizer.py---------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===-----------------------------------------------------------------------===//

"""Redaction of secrets from command output and log records."""

from __future__ import annotations

REDACTED = "[REDACTED_TOKEN]"


class TokenSanitizer:
    def __init__(self, token: str | None = None) -> None:
        self._tokens = {token} if token else set()

    def add(self, token: str | None) -> None:
        if token:
            self._tokens.add(token)

    def clean(self, value: str | None) -> str:
        if value is None:
            return ""
        for token in self._tokens:
            value = value.replace(token, REDACTED)
        return value
