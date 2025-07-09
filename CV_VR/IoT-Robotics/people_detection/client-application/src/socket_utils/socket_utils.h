//===--socket_utils.h------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//
#ifndef SOCKET_UTILS_H
#define SOCKET_UTILS_H

#define SOCKET_PORT_NO 58001
#define MAX_CONNECTIONS 3

#define SOCKET_ERROR_SUCCESS 0
#define SOCKET_ERROR_FAILURE -1


// #define ENABLE_LOGS

#ifdef ENABLE_LOGS
	#undef SOCKET_PRINT_MSG
  #define SOCKET_PRINT_MSG(msg,...) \
    printf(msg, ## __VA_ARGS__)
#else
	#undef SOCKET_PRINT_MSG
  #define SOCKET_PRINT_MSG(msg,...)
#endif

int socket_server_init(const char *ipv4_addr, const unsigned int port_no);

int socket_client_init(const char *ipv4_addr, const unsigned int port_no);

int socket_server_deinit();

int socket_client_deinit();

int socket_wait_for_newconn(const int server_fd);

int socket_publish_message(const int socket_id, const unsigned char *buf, const unsigned int buf_size);

int socket_receive_message(const int socket_id, unsigned char *buf, const unsigned int buf_size, unsigned int *recv_buf_size);

#endif // SOCKET_UTILS_H
