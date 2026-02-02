#===--demo_animations.py--------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
#!/usr/bin/env python3
"""
Demo script to show all available AI animation modes.
"""

import subprocess
import sys

animations = {
    'edge-pulse': 'AI: Edge detection with pulsing Canny thresholds',
    'morph': 'AI: Morphological erosion/dilation animation',
    'contour-wave': 'AI: Contour detection with wave emphasis',
    'zoom': 'AI: Breathing zoom in/out effect',
    'wave-distort': 'AI: Sinusoidal wave distortion',
    'saliency': 'AI: Saliency-based focus animation',
    'threshold': 'Classic: Threshold sweep animation',
    'rotate': 'Classic: Rotation animation',
    'flip': 'Classic: Flip animation'
}

def run_animation(anim_type, image_file='test.png', frames=6, threshold=64):
    """Run a single animation demo."""
    print(f"\n{'='*60}")
    print(f"Animation: {anim_type}")
    print(f"Description: {animations[anim_type]}")
    print('='*60)
    
    cmd = [
        'python', 'img_to_13x8_u32.py',
        image_file,
        '--threshold', str(threshold),
        '--animate', anim_type,
        '--frames', str(frames)
    ]
    
    try:
        # Just show the frames, animation preview will run and user can Ctrl+C
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nAnimation interrupted by user")
    except Exception as e:
        print(f"Error: {e}")


def main():
    if len(sys.argv) < 2:
        print("Available AI Animation Modes:")
        print("="*60)
        for anim, desc in animations.items():
            print(f"  {anim:15s} - {desc}")
        print("\nUsage:")
        print(f"  python {sys.argv[0]} <animation-type> [image.png] [threshold]")
        print("\nExamples:")
        print(f"  python {sys.argv[0]} edge-pulse")
        print(f"  python {sys.argv[0]} morph Designer.png 64")
        print(f"  python {sys.argv[0]} zoom myimage.png 100")
        return
    
    anim_type = sys.argv[1]
    image_file = sys.argv[2] if len(sys.argv) > 2 else 'Designer.png'
    threshold = int(sys.argv[3]) if len(sys.argv) > 3 else 64
    
    if anim_type not in animations:
        print(f"Error: Unknown animation type '{anim_type}'")
        print(f"Available: {', '.join(animations.keys())}")
        return
    
    run_animation(anim_type, image_file, frames=8, threshold=threshold)


if __name__ == '__main__':
    main()
