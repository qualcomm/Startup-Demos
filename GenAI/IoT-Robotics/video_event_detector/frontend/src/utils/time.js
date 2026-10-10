/*
 *===--time.js-----------------------------------------------------------===//
 * Part of the Startup-Demos Project, under the MIT License
 * See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
 * for license information.
 * Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
 * SPDX-License-Identifier: MIT
 *===----------------------------------------------------------------------===//
 */

export function formatTime(value) {
  if (!Number.isFinite(value) || value < 0) {
    return '00:00'
  }

  const totalSeconds = Math.floor(value)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const parts = hours > 0 ? [hours, minutes, seconds] : [minutes, seconds]

  return parts.map((part) => String(part).padStart(2, '0')).join(':')
}
