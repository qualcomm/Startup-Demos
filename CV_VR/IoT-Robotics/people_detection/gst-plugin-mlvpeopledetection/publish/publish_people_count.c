//===--publish_people_count.c----------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <ifaddrs.h>
#include <netdb.h>

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

int GetDefaultGw(char *host_ip)
{
    FILE *route_file;
    char line[100], *interface = NULL, *gateway, *saveptr, host[NI_MAXHOST];
    int result = SOCKET_ERROR_FAILURE, name_info_status;
    struct ifaddrs *ifaddr, *ifa;

    route_file = fopen("/proc/net/route", "r");
    if (route_file == NULL) {
	printf("Error opening /proc/net/route\n");
        return SOCKET_ERROR_FAILURE;
    }

    while (fgets(line, sizeof(line), route_file)) {
        interface = strtok_r(line, " \t", &saveptr);
        gateway = strtok_r(NULL, " \t", &saveptr);

        if (interface != NULL && gateway != NULL && strcmp(gateway, "00000000") == SOCKET_ERROR_SUCCESS) {
            SOCKET_PRINT_MSG("Default interface is: %s\n", interface);
            break;
        }
    }
    fclose(route_file);

    if (interface == NULL) {
        printf("No default gateway found\n");
        return SOCKET_ERROR_FAILURE;
    }

    if (getifaddrs(&ifaddr) == SOCKET_ERROR_FAILURE) {
	printf("Error getting interface addresses\n");
        return SOCKET_ERROR_FAILURE;
    }

    for (ifa = ifaddr; ifa != NULL; ifa = ifa->ifa_next) {
        if (ifa->ifa_addr == NULL || ifa->ifa_addr->sa_family != AF_INET)
            continue;

        name_info_status = getnameinfo(ifa->ifa_addr, sizeof(struct sockaddr_in), host, NI_MAXHOST, NULL, 0, NI_NUMERICHOST);
        if (name_info_status != SOCKET_ERROR_SUCCESS) {
            printf("getnameinfo() failed: %s\n", gai_strerror(name_info_status));
            freeifaddrs(ifaddr);
            return SOCKET_ERROR_FAILURE;
        }

        if (strcmp(ifa->ifa_name, interface) == SOCKET_ERROR_SUCCESS) {
            SOCKET_PRINT_MSG("\tInterface: <%s>\n", ifa->ifa_name);
            SOCKET_PRINT_MSG("Address: %s\n", host);
            strcpy(host_ip, host);
            result = SOCKET_ERROR_SUCCESS;
            break;
        }
    }

    freeifaddrs(ifaddr);
    return result;
}

int people_counter_server_init()
{
    int server_fd, socket_in;
    char host_ip[NI_MAXHOST];

    if (GetDefaultGw(host_ip) != SOCKET_ERROR_SUCCESS) {
        printf("GetDefaultGw failed\n");
        return (SOCKET_ERROR_FAILURE);
    }

    if ((server_fd = socket_server_init(host_ip, SOCKET_PORT_NO)) == SOCKET_ERROR_FAILURE) {
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