#===--animation_showcase.py-----------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
#!/usr/bin/env python3
"""
Continuously loop through all animation types with live preview.
"""

import sys
import time
import os
from PIL import Image

# Import functions from img_to_13x8_u32
sys.path.insert(0, os.path.dirname(__file__))
from img_to_13x8_u32 import (
    image_to_13x8_bits, pack_bits_to_u32, bits_to_ascii,
    generate_edge_pulse_animation, generate_morph_animation,
    generate_contour_wave_animation, generate_zoom_animation,
    generate_wave_distort_animation, generate_saliency_animation,
    generate_threshold_fallback
)

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

class Args:
    """Simple args class to mimic argparse."""
    def __init__(self):
        self.threshold = 64
        self.invert = False
        self.rotate = 0
        self.mirror = False
        self.flip = False
        self.frames = 8
        self.frame_name = 'frame'

def show_animation_live(name, anim_type, duration=10, frames=8):
    """Show animation live for specified duration."""
    try:
        print(f"Generating {name}...")

        # Load image
        img = Image.open('test.png')

        # Create args object
        args = Args()
        args.frames = frames

        # Generate frames based on animation type
        if anim_type == 'edge-pulse':
            frames_data = generate_edge_pulse_animation(img, args)
        elif anim_type == 'morph':
            frames_data = generate_morph_animation(img, args)
        elif anim_type == 'contour-wave':
            frames_data = generate_contour_wave_animation(img, args)
        elif anim_type == 'zoom':
            frames_data = generate_zoom_animation(img, args)
        elif anim_type == 'wave-distort':
            frames_data = generate_wave_distort_animation(img, args)
        elif anim_type == 'saliency':
            frames_data = generate_saliency_animation(img, args)
        elif anim_type == 'threshold':
            frames_data = generate_threshold_fallback(img, args)
        elif anim_type == 'rotate':
            # Generate rotation frames manually
            frames_data = []
            angles = [i * 360 // frames for i in range(frames)]
            for angle in angles:
                bits = image_to_13x8_bits(img.copy(), threshold=64, invert=False,
                                         rotate=angle, mirror=False, flip=False)
                words = pack_bits_to_u32(bits)
                frames_data.append((words, bits))
        else:
            print(f"Unknown animation type: {anim_type}")
            return

        if not frames_data:
            print(f"No frames generated for {name}")
            return

        # Display frames in loop for duration
        start_time = time.time()
        frame_idx = 0
        fps = 5  # 5 frames per second

        while time.time() - start_time < duration:
            clear_screen()
            _, bits = frames_data[frame_idx % len(frames_data)]

            print(f"{'='*60}")
            print(f"ANIMATION: {name.upper()}")
            print(f"Type: {anim_type} | Frame: {frame_idx % len(frames_data) + 1}/{len(frames_data)}")
            print(f"Time: {int(time.time() - start_time)}s / {duration}s")
            print(f"{'='*60}\n")

            print(bits_to_ascii(bits))

            time.sleep(1.0 / fps)
            frame_idx += 1

    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"Error with {name}: {e}")
        import traceback
        traceback.print_exc()
        time.sleep(3)

def main():
    animations = [
        ('Edge Pulse - AI Edge Detection', 'edge-pulse'),
        ('Morphological - AI Erosion/Dilation', 'morph'),
        ('Contour Wave - AI Contour Detection', 'contour-wave'),
        ('Zoom - AI Breathing Effect', 'zoom'),
        ('Wave Distort - AI Image Warping', 'wave-distort'),
        ('Saliency - AI Focus Detection', 'saliency'),
        ('Threshold Sweep - Classic', 'threshold'),
        ('Rotation - Classic', 'rotate'),
    ]

    print("="*60)
    print("LED MATRIX ANIMATION SHOWCASE")
    print("Each animation plays for 10 seconds")
    print("Press Ctrl+C to stop")
    print("="*60)
    time.sleep(2)

    try:
        while True:  # Loop forever
            for name, anim_type in animations:
                show_animation_live(name, anim_type, duration=10, frames=8)
                time.sleep(0.5)  # Brief pause between animations
    except KeyboardInterrupt:
        clear_screen()
        print("\n" + "="*60)
        print("Animation showcase stopped by user")
        print("="*60)

if __name__ == '__main__':
    main()
