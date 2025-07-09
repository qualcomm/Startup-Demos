//===--receive_people_count.c----------------------------------------------===//
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

#include <socket_utils/socket_utils.h>

void print_group_counts(const char* message) {
    int zone_counts[5] = {0};
    sscanf(message, "Group counts: %d, %d, %d, %d, %d",
           &zone_counts[0], &zone_counts[1], &zone_counts[2],
           &zone_counts[3], &zone_counts[4]);

    printf("Zone 1: %d people\n", zone_counts[0]);
    printf("Zone 2: %d people\n", zone_counts[1]);
    printf("Zone 3: %d people\n", zone_counts[2]);
    printf("Zone 4: %d people\n", zone_counts[3]);
    printf("Zone 5: %d people\n", zone_counts[4]);
}

int main(int argc, char *argv[]) {
    int socket_in;
    char buffer[1024] = {0};
    if (argc < 2) {
        printf("Invalid argument\n");
        return SOCKET_ERROR_FAILURE;
    }

    const char* ip_address = argv[1];

    // Validate IP address
    struct sockaddr_in sa;
    if (inet_pton(AF_INET, ip_address, &(sa.sin_addr)) == SOCKET_ERROR_SUCCESS) {
        printf("Invalid IP address format. Please provide a valid IPv4 address (e.g., 192.168.1.1).\n");
        return SOCKET_ERROR_FAILURE;
    }

    if ((socket_in = socket_client_init(ip_address, SOCKET_PORT_NO)) == SOCKET_ERROR_FAILURE) {
        printf("socket_client_init failed\n");
        return SOCKET_ERROR_FAILURE;
    }

    while (1) {
        if (socket_receive_message(socket_in, (unsigned char*)buffer, sizeof(buffer), NULL) != SOCKET_ERROR_SUCCESS) {
            printf("socket_receive_message failed\n");
            break;
        } else {
            printf("Msg from server: %s\n", buffer);
            print_group_counts(buffer);
        }
    }

    if (socket_client_deinit() != SOCKET_ERROR_SUCCESS) {
        printf("socket_client_deinit failed\n");
        return SOCKET_ERROR_FAILURE;
    }

    return SOCKET_ERROR_SUCCESS;
}
