//===--publish_people_count.h----------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//
#ifndef PUBLISH_PEOPLE_COUNT_H
#define PUBLISH_PEOPLE_COUNT_H

// Function prototypes
int publish_group_count(int* group_people_count, int count);
int display_people_counter_init();

// Global variable
extern int g_socket_server_in;

#endif // PUBLISH_PEOPLE_COUNT_H