//===--socket_utils.c------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//
// Server side C/C++ program to demonstrate Socket
// programming
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#include <arpa/inet.h>

#include "socket_utils.h"

struct sockaddr_in g_socket_in_addr;
int g_socket_server_fd, g_socket_client_fd;
int g_socket_server_id, g_socket_client_id;

#ifdef SOCKET_UTILS_H

int socket_server_init(const char *ipv4_addr, const unsigned int port_no)
{
  int server_fd;
  struct sockaddr_in address;
  
  SOCKET_PRINT_MSG("socket_server_init ++\n");

  // Creating socket file descriptor
  if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
	SOCKET_PRINT_MSG("socket file decriptor creation failed\n");
    return (SOCKET_ERROR_FAILURE);
  }

  //Set Address and Port
  address.sin_family = AF_INET;
  address.sin_addr.s_addr = inet_addr(ipv4_addr);
  address.sin_port = htons(port_no);
  
  // Forcefully attaching socket to the port
  if (bind(server_fd, (struct sockaddr*)&address, sizeof(address)) < 0) {
    SOCKET_PRINT_MSG("socket bind failed\n");
    return (SOCKET_ERROR_FAILURE);
  }
  if (listen(server_fd, 3) < 0) {
    SOCKET_PRINT_MSG("socket listen failed\n");
    return (SOCKET_ERROR_FAILURE);
  }

  g_socket_server_fd = server_fd;

  SOCKET_PRINT_MSG("socket_server_init --\n");

  return server_fd;
}

int socket_client_init(const char *ipv4_addr, const unsigned int port_no)
{
  int client_fd, socket_id;
  struct sockaddr_in address;
  
  SOCKET_PRINT_MSG("socket_server_init ++\n");

  // Creating socket file descriptor
  if ((socket_id = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
	SOCKET_PRINT_MSG("socket file decriptor creation failed\n");
    return (SOCKET_ERROR_FAILURE);
  }

  //Set Address and Port
  address.sin_family = AF_INET;
  address.sin_addr.s_addr = inet_addr(ipv4_addr);
  address.sin_port = htons(port_no);
  
  // Forcefully attaching socket to the port
  if ((client_fd = connect(socket_id, (struct sockaddr*)&address, sizeof(address))) < 0) {
    SOCKET_PRINT_MSG("socket bind failed\n");
    return (SOCKET_ERROR_FAILURE);
  }

  g_socket_client_fd = client_fd;

  SOCKET_PRINT_MSG("socket_server_init --\n");

  return socket_id;
}

int socket_server_deinit()
{
  SOCKET_PRINT_MSG("socket_server_deinit ++\n");
  close(g_socket_client_id);

  // closing the listening socket
  shutdown(g_socket_server_fd, SHUT_RDWR);

  SOCKET_PRINT_MSG("socket_server_deinit --\n");

  return SOCKET_ERROR_SUCCESS;
}

int socket_client_deinit()
{
  SOCKET_PRINT_MSG("socket_client_deinit ++\n");
  close(g_socket_client_fd);
  SOCKET_PRINT_MSG("socket_client_deinit --\n");

  return SOCKET_ERROR_SUCCESS;
}

int socket_wait_for_newconn(const int server_fd)
{
  int socket_in;
  struct sockaddr_in address;
  int addrlen = sizeof(address);

  SOCKET_PRINT_MSG("socket_wait_for_newconn ++\n");

  if ((socket_in= accept(server_fd, (struct sockaddr*)&address, (socklen_t*)&addrlen))< 0) {
	SOCKET_PRINT_MSG("socket accept failed\n");
    return (SOCKET_ERROR_FAILURE);
  }

  memcpy(&g_socket_in_addr, &address, addrlen) ;
  g_socket_client_id = socket_in;

  SOCKET_PRINT_MSG("socket_wait_for_newconn --\n");

  return socket_in;
}

int socket_publish_message(const int socket_id, const unsigned char *buf, const unsigned int buf_size)
{
  unsigned int send_bytes;

  SOCKET_PRINT_MSG("socket_publish_message size %d ++\n", buf_size);
  SOCKET_PRINT_MSG("socket_publish_message socket_id %d buf %d buf_size = %d \n",socket_id, buf, buf_size);

  if ((send_bytes = send(socket_id, buf, buf_size, 0)) != buf_size){
    SOCKET_PRINT_MSG("socket_publish_message failed send_bytes = %d\n",send_bytes);
    return (SOCKET_ERROR_FAILURE);
  }
  
  SOCKET_PRINT_MSG("socket_publish_message send_bytes %d--\n", send_bytes);

  return SOCKET_ERROR_SUCCESS;
}

int socket_receive_message(const int socket_id, unsigned char *buf, const unsigned int buf_size, unsigned int *recv_buf_size)
{
  unsigned int recv_size;

  SOCKET_PRINT_MSG("socket_receive_message ++\n");
  SOCKET_PRINT_MSG("socket_receive_message socket_id %d buf %d buf_size = %d recv_buf_size %d \n",socket_id, buf, buf_size, recv_buf_size);

  if ((recv_size = recv(socket_id, buf, buf_size, 0)) <= 0 ){
    SOCKET_PRINT_MSG("socket_receive_message failed\n");
    return (SOCKET_ERROR_FAILURE);
  }

  if(recv_buf_size != NULL) {
    recv_buf_size[0] = recv_size;
  }
  SOCKET_PRINT_MSG("socket_receive_message recv_size %d --\n", recv_size);

  return SOCKET_ERROR_SUCCESS;
}

#endif
