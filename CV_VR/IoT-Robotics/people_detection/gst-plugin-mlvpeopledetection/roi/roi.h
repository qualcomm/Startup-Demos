//===--roi.h--------------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//
#ifndef ROI_H
#define ROI_H
 
typedef struct {
  float x;
  float y;
  float width;
  float height;
  unsigned int color;
} ROI;
 
typedef struct {
	ROI *roi;
	unsigned int size;
} ROI_LIST;
 
typedef struct {
	ROI_LIST *roi_list;
	unsigned int size;
} ROI_LIST_ARRAY;
 
#define PC_LUT_SIZE_X 80
#define PC_LUT_SIZE_Y 50

#define ROI_ERROR_SUCCESS 0
#define ROI_ERROR_FAILURE -1

int people_counter_init ();
int people_counter_get_group_id (float x, float y, float w, float h);

// #define ENABLE_LOGS

#ifdef ENABLE_LOGS
	#undef ROI_PRINT_MSG
  #define ROI_PRINT_MSG(msg,...) \
    printf(msg, ## __VA_ARGS__)
#else
	#undef ROI_PRINT_MSG
  #define ROI_PRINT_MSG(msg,...)
#endif

#endif // ROI_H