//===--publish_people_count.c----------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//
//Server side C/C++ program to demonstrate Socket
//programming
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#include <arpa/inet.h>

#include <socket_utils/socket_utils.h>
#include "publish_people_count.h"


int g_socket_server_in;

int publish_group_count(int* group_people_count, int count)
{
    char message[256];
    snprintf(message, sizeof(message), "Group counts: %d, %d, %d, %d, %d\n",
             group_people_count[0], group_people_count[1], group_people_count[2],
             group_people_count[3], group_people_count[4]);

    if (socket_publish_message(g_socket_server_in, (const unsigned char*)message, strlen(message)) != SOCKET_ERROR_SUCCESS) {
        printf("socket_publish_message failed\n");
        return (SOCKET_ERROR_FAILURE);
    }
    return SOCKET_ERROR_SUCCESS;
}

int people_counter_server_init()
{
    int server_fd, socket_in;
    if ((server_fd = socket_server_init("10.91.59.154", SOCKET_PORT_NO)) == SOCKET_ERROR_FAILURE) {
        printf("socket_server_init failed\n");
        return (SOCKET_ERROR_FAILURE);
    }

    if ((socket_in = socket_wait_for_newconn(server_fd)) == SOCKET_ERROR_FAILURE) {
        printf("socket_wait_for_newconn failed\n");
        return (SOCKET_ERROR_FAILURE);
    }
    g_socket_server_in = socket_in;
    return SOCKET_ERROR_SUCCESS;
}

int display_people_counter_init()
{
    SOCKET_PRINT_MSG("display people_counter_init ++ \n");
    if (people_counter_server_init() != SOCKET_ERROR_SUCCESS) {
        printf("people_counter_server_init failed \n");
        return SOCKET_ERROR_FAILURE;
    }
    SOCKET_PRINT_MSG("display people_counter_init -- \n");
    return SOCKET_ERROR_SUCCESS;
}