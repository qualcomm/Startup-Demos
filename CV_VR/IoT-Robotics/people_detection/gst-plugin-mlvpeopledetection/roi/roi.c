//===--roi.c--------------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#include "roi.h"
#include "roi_config.h"

// For People Counter
static ROI_LIST_ARRAY *g_roi_list_array;
static unsigned int LUT_ROI[PC_LUT_SIZE_X][PC_LUT_SIZE_Y];


static int
people_counter_print_roi ()
{
	unsigned int i, j;
	
	ROI_PRINT_MSG("people_counter_print_roi ++\n");

	for(i =0; i<PC_LUT_SIZE_Y; i++)
	{
		for(j=0; j<PC_LUT_SIZE_X; j++)
		{
			ROI_PRINT_MSG("%d",LUT_ROI[j][i]);
		}
		ROI_PRINT_MSG("\n");
	}
		
	ROI_PRINT_MSG("people_counter_print_roi -- \n");
	return ROI_ERROR_SUCCESS;
}

int
people_counter_get_group_id (float x, float y, float w, float h)
{
	unsigned int start_x = x * (PC_LUT_SIZE_X-1);
	unsigned int start_y = y * (PC_LUT_SIZE_Y-1);
	unsigned int end_x   = (x + w) *  (PC_LUT_SIZE_X-1);
	unsigned int end_y   = (y + h) * (PC_LUT_SIZE_Y-1);
	
	unsigned int g1 = LUT_ROI[start_x][start_y];
	unsigned int g2 = LUT_ROI[end_x][end_y];
	if( g1 == g2)
		return g1;
		
	return ROI_ERROR_FAILURE;
}

static int
people_counter_fill_roi (unsigned int group_id, ROI *roi)
{
	unsigned int start_x =  roi->x * (PC_LUT_SIZE_X-1);
	unsigned int start_y =  roi->y * (PC_LUT_SIZE_Y-1);
	unsigned int end_x   = (roi->x + roi->width) *  (PC_LUT_SIZE_X-1);
	unsigned int end_y   = (roi->y + roi->height) * (PC_LUT_SIZE_Y-1);
	unsigned int i, j;
	
	ROI_PRINT_MSG("people_counter_fill_roi ++\n");
	ROI_PRINT_MSG("people_counter_fill_roi %f, %f, %f, %f \n", roi->x, roi->y, roi->width, roi->height);
	ROI_PRINT_MSG("people_counter_fill_roi %d, %d, %d, %d \n", start_x, start_y, end_x, end_y);

	for(i =start_x; i<end_x; i++)
		for(j=start_y; j<end_y; j++)
			LUT_ROI[i][j]=group_id;
		
	ROI_PRINT_MSG("people_counter_fill_roi -- \n");
	return ROI_ERROR_SUCCESS;
}

static int
people_counter_roi_init ()
{
	unsigned int i,j;
	g_roi_list_array = &roi_list_array;
	ROI_PRINT_MSG("people_counter_roi_init %d ++ \n", g_roi_list_array->size);
	for(i =0; i<g_roi_list_array->size; i++)
		for(j=0; j<g_roi_list_array->roi_list[i].size; j++)
			people_counter_fill_roi(i+1, &g_roi_list_array->roi_list[i].roi[j]);
	
	people_counter_print_roi();
		
	ROI_PRINT_MSG("people_counter_roi_init -- \n");
	return ROI_ERROR_SUCCESS;
}

int
people_counter_init ()
{
	ROI_PRINT_MSG("people_counter_init ++ \n");
	if(!people_counter_roi_init())
	{
		ROI_PRINT_MSG("people_counter_roi_init failed \n");
		return ROI_ERROR_FAILURE;
		
	}
	ROI_PRINT_MSG("people_counter_init -- \n");
	return ROI_ERROR_SUCCESS;
}