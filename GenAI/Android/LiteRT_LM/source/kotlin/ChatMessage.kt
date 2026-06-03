/*
 *===--ChatMessage.kt---------------------------------------------------===//
 * Part of the Startup-Demos Project, under the MIT License
 * See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
 * for license information.
 * Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
 * SPDX-License-Identifier: MIT
 *===----------------------------------------------------------------------===//
 */

package com.example.litertlm

data class ChatMessage(
    val role: String, // "user" or "model"
    val text: String
)
