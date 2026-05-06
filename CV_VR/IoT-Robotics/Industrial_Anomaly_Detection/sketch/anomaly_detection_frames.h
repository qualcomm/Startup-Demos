#ifndef ANOMALY_DETECTION_FRAMES_H
#define ANOMALY_DETECTION_FRAMES_H

#include <stdint.h>

//===----------------------------------------------------------------------===//
// FIRE ANIMATION FRAMES
//===----------------------------------------------------------------------===//
const uint32_t fire_frame_0[] = {0x00001000, 0x800e00f0, 0x07c03f01, 0xf8000000};
const uint32_t fire_frame_1[] = {0x00000000, 0x800600f0, 0x07c03f01, 0xf8000000};
const uint32_t fire_frame_2[] = {0x00000000, 0x80060078, 0x07e03f03, 0xf8000000};
const uint32_t fire_frame_3[] = {0x00000000, 0x80060078, 0x07e07f03, 0xf0000000};
const uint32_t fire_frame_4[] = {0x00000000, 0xc0060038, 0x07c07e03, 0xf0000000};
const uint32_t fire_frame_5[] = {0x00000000, 0xc0060038, 0x07c07e03, 0xf0000000};
const uint32_t fire_frame_6[] = {0x00001000, 0x40060078, 0x07c07e03, 0xf0000000};
const uint32_t fire_frame_7[] = {0x00000800, 0x40060078, 0x07c07e03, 0xf0000000};
const uint32_t fire_frame_8[] = {0x02000800, 0x40060078, 0x0fc07e03, 0xf0000000};
const uint32_t fire_frame_9[] = {0x02000800, 0xc00e00f0, 0x0fc07f01, 0xf8000000};
const uint32_t fire_frame_10[] = {0x00000800, 0xc00e00f0, 0x0fc07f01, 0xf8000000};
const uint32_t fire_frame_11[] = {0x00001000, 0x800e00f0, 0x0fc03f01, 0xf8000000};
const uint32_t fire_frame_12[] = {0x02001000, 0x800e00f0, 0x07c03f01, 0xf8000000};
const uint32_t fire_frame_13[] = {0x02001001, 0x800c00f0, 0x07c03f01, 0xf8000000};
const uint32_t fire_frame_14[] = {0x00001000, 0x800c00f0, 0x07c03f01, 0xf8000000};
const uint32_t fire_frame_15[] = {0x00001000, 0x800e00f0, 0x07c03f01, 0xf8000000};

const uint32_t* const fire_frames[] = {
  fire_frame_0, fire_frame_1, fire_frame_2, fire_frame_3,
  fire_frame_4, fire_frame_5, fire_frame_6, fire_frame_7,
  fire_frame_8, fire_frame_9, fire_frame_10, fire_frame_11,
  fire_frame_12, fire_frame_13, fire_frame_14, fire_frame_15
};

//===----------------------------------------------------------------------===//
// LEAKAGE ANIMATION FRAMES
//===----------------------------------------------------------------------===//
const uint32_t leak_frame_0[] = {0x7ff1bf00, 0x100c0070, 0x07c01e00, 0xf0000000};
const uint32_t leak_frame_1[] = {0x7fe1ff00, 0x300c0070, 0x07c03e00, 0xf0000000};
const uint32_t leak_frame_2[] = {0x7fe1ff00, 0x00040070, 0x03c03e01, 0xf0000000};
const uint32_t leak_frame_3[] = {0x7fe1ff00, 0x00040070, 0x03c03e01, 0xe0000000};
const uint32_t leak_frame_4[] = {0x7fe1ff00, 0x00040030, 0x07c03e01, 0xe0000000};
const uint32_t leak_frame_5[] = {0x7ff1ff00, 0x00060070, 0x07c03e01, 0xe0000000};
const uint32_t leak_frame_6[] = {0x7ff1ff04, 0x00060070, 0x07c03c01, 0xe0000000};
const uint32_t leak_frame_7[] = {0x7ff1ff04, 0x00060070, 0x07803c01, 0xe0000000};
const uint32_t leak_frame_8[] = {0x7ff1fb84, 0x80040070, 0x07803c01, 0xe0000000};
const uint32_t leak_frame_9[] = {0x3ff1f380, 0x800c00f0, 0x07c03e01, 0xe0000000};
const uint32_t leak_frame_10[] = {0x3ff1f380, 0x800c00f0, 0x07c03e00, 0xe0000000};
const uint32_t leak_frame_11[] = {0x3ff1e780, 0x800c00f0, 0x07c03e00, 0xf0000000};
const uint32_t leak_frame_12[] = {0x3ff18f81, 0x800c00f0, 0x07c01e00, 0xf0000000};
const uint32_t leak_frame_13[] = {0x7ff39f81, 0x000c00f0, 0x07c01e00, 0xf0000000};
const uint32_t leak_frame_14[] = {0x7ff3bf81, 0x100c00f0, 0x07c01e00, 0xf0000000};
const uint32_t leak_frame_15[] = {0x7ff1bf00, 0x100c0070, 0x07c01e00, 0xf0000000};

const uint32_t* const leak_frames[] = {
  leak_frame_0, leak_frame_1, leak_frame_2, leak_frame_3,
  leak_frame_4, leak_frame_5, leak_frame_6, leak_frame_7,
  leak_frame_8, leak_frame_9, leak_frame_10, leak_frame_11,
  leak_frame_12, leak_frame_13, leak_frame_14, leak_frame_15
};

//===----------------------------------------------------------------------===//
// OK ANIMATION FRAMES (Right Arrow)
//===----------------------------------------------------------------------===//
const uint32_t ok_frame_0[] = {0x17400000, 0x60160060, 0x00000003, 0xf8000000};
const uint32_t ok_frame_1[] = {0x00000600, 0x601600e0, 0x02000000, 0x00000000};
const uint32_t ok_frame_2[] = {0x40120690, 0x64b624e1, 0x22090048, 0x02000000};
const uint32_t ok_frame_3[] = {0x804c0660, 0x733718f0, 0xc3060030, 0x01000000};
const uint32_t ok_frame_4[] = {0x804c0660, 0x733718f0, 0xc3060030, 0x01000000};
const uint32_t ok_frame_5[] = {0x40120690, 0x64b624f1, 0x23090048, 0x02000000};
const uint32_t ok_frame_6[] = {0x40120690, 0x64b624e1, 0x22090048, 0x02000000};
const uint32_t ok_frame_7[] = {0x20210408, 0x685642e2, 0x10108084, 0x04000000};
const uint32_t ok_frame_8[] = {0x00000000, 0x601e0060, 0x00000100, 0x00000000};
const uint32_t ok_frame_9[] = {0x00000000, 0x400e0060, 0x00000000, 0x00000000};
const uint32_t ok_frame_10[] = {0x00000000, 0x00060020, 0x00000000, 0x00000000};
const uint32_t ok_frame_11[] = {0x00000000, 0x00060020, 0x00000000, 0x00000000};
const uint32_t ok_frame_12[] = {0x00000000, 0x00060020, 0x00000000, 0x00000000};
const uint32_t ok_frame_13[] = {0x00000000, 0x00060060, 0x00000000, 0x00000000};
const uint32_t ok_frame_14[] = {0x00000000, 0x600e0060, 0x00000000, 0x00000000};
const uint32_t ok_frame_15[] = {0x17400000, 0x60160060, 0x00000003, 0xf8000000};

const uint32_t* const ok_frames[] = {
  ok_frame_0, ok_frame_1, ok_frame_2, ok_frame_3,
  ok_frame_4, ok_frame_5, ok_frame_6, ok_frame_7,
  ok_frame_8, ok_frame_9, ok_frame_10, ok_frame_11,
  ok_frame_12, ok_frame_13, ok_frame_14, ok_frame_15
};

// Frame count constant
const int ANIMATION_FRAME_COUNT = 16;

#endif // ANOMALY_DETECTION_FRAMES_H
