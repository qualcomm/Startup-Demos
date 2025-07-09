//===--roi_config.h--------------------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//
#ifndef ROI_CONFIG_H
#define ROI_CONFIG_H

static ROI rois_group1[] = {
  {0.0, 0.0, 0.5, 0.5, 0xFF0000}, // Red
  {0.0, 0.5, 0.5, 0.3, 0xFF0000}, // Red
  {0.0, 0.8, 0.5, 0.2, 0xFF0000}, // Red
};
 
static ROI rois_group2[] = {
  {0.5, 0.0, 0.3, 0.5, 0x00FF00}, // Green
  {0.5, 0.5, 0.3, 0.5, 0x00FF00}, // Green
};
 
static ROI rois_group3[] = {
  {0.8, 0.0, 0.2, 0.5, 0x00FF00}, // Green
  {0.8, 0.5, 0.2, 0.5, 0x00FF00}, // Green
};
 
static ROI_LIST roi_list_cfg[] = {
  {
    rois_group1,
    sizeof(rois_group1)/sizeof(ROI),
  },
  {
    rois_group2,
    sizeof(rois_group2)/sizeof(ROI),
  },
  {
    rois_group3,
    sizeof(rois_group3)/sizeof(ROI),
  },	
};

static ROI_LIST_ARRAY roi_list_array = {
    roi_list_cfg,
    sizeof(roi_list_cfg)/sizeof(ROI_LIST),
};
 
#endif // ROI_CONFIG_H