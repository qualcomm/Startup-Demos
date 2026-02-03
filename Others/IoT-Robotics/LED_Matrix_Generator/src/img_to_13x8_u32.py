#===--img_to_13x8_u32.py--------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
#!/usr/bin/env python3
"""
img_to_13x8_u32.py

Converts an input image to a 13×8 monochrome bitmap and packs it into
4 uint32 values (128 bits total, 104 bits used).

Packing scheme (MSB-first, row-major):
- Pixels are linearized: k = row*13 + col (row: 0-7, col: 0-12)
- word_index = k // 32
- bit_position = 31 - (k % 32)  # MSB-first within each 32-bit word
- MSB (bit 31) of W[0] corresponds to pixel at row=0, col=0
- Last 24 bits of W[3] remain 0 (only 104 bits used)
"""

import sys
import argparse
import numpy as np
from PIL import Image

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from skimage import filters, morphology, feature
    from scipy import ndimage
    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False


def crop_top_bottom_to_aspect(img, target_w=13, target_h=8):
    """
    Crop image to target aspect ratio by removing top/bottom only.
    
    Args:
        img: PIL Image object
        target_w: target width ratio (13)
        target_h: target height ratio (8)
    
    Returns:
        Cropped PIL Image
    """
    width, height = img.size
    target_aspect = target_h / target_w  # 8/13
    desired_height = round(width * target_aspect)
    
    if height > desired_height:
        # Need to crop vertically
        crop_amount = height - desired_height
        top_crop = crop_amount // 2
        bottom_crop = crop_amount - top_crop
        
        # Crop box: (left, top, right, bottom)
        box = (0, top_crop, width, height - bottom_crop)
        return img.crop(box)
    else:
        # Height is less or equal to desired - just return as-is
        # Will be stretched slightly during resize
        return img


def image_to_13x8_bits(img, threshold=128, invert=False, rotate=0, mirror=False, flip=False):
    """
    Convert PIL image to 13×8 binary bitmap.
    
    Args:
        img: PIL Image object
        threshold: grayscale threshold (0-255)
        invert: if True, invert the binary output
        rotate: rotation angle (0, 90, 180, 270)
        mirror: if True, mirror horizontally (left-right)
        flip: if True, flip vertically (top-bottom)
    
    Returns:
        2D list: bits[row][col] where row in 0-7, col in 0-12
    """
    # Handle RGBA by compositing on white background
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
        img = background
    
    # Convert to grayscale
    img = img.convert('L')
    
    # Crop to aspect ratio
    img = crop_top_bottom_to_aspect(img, 13, 8)
    
    # Resize to 13×8
    try:
        # Try newer PIL API
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        # Fall back to older API
        resample = Image.LANCZOS
    
    img = img.resize((13, 8), resample=resample)
    
    # Apply rotation if specified
    if rotate == 90:
        img = img.rotate(-90, expand=True)
    elif rotate == 180:
        img = img.rotate(180)
    elif rotate == 270:
        img = img.rotate(90, expand=True)
    
    # Apply mirror/flip
    if mirror:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if flip:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    
    # Ensure size is still 13×8 after transformations
    if img.size != (13, 8):
        img = img.resize((13, 8), resample=resample)
    
    # Convert to binary bitmap
    pixels = list(img.getdata())
    bits = []
    
    for row in range(8):
        row_bits = []
        for col in range(13):
            pixel_val = pixels[row * 13 + col]
            if invert:
                is_on = pixel_val < threshold
            else:
                is_on = pixel_val >= threshold
            row_bits.append(1 if is_on else 0)
        bits.append(row_bits)
    
    return bits


def pack_bits_to_u32(bits):
    """
    Pack 13×8 bitmap into 4 uint32 values.
    
    Packing scheme:
    - Linearize pixels in row-major order: k = row*13 + col
    - word_index = k // 32
    - bit_position = 31 - (k % 32)  # MSB-first
    - W[0] bit 31 = pixel at (row=0, col=0)
    - Only 104 bits used; last 24 bits of W[3] remain 0
    
    Args:
        bits: 2D list bits[8][13]
    
    Returns:
        List of 4 uint32 values
    """
    words = [0, 0, 0, 0]
    
    for row in range(8):
        for col in range(13):
            k = row * 13 + col
            word_index = k // 32
            bit_position = 31 - (k % 32)
            
            if bits[row][col]:
                words[word_index] |= (1 << bit_position)
    
    # Ensure values are within uint32 range
    words = [w & 0xFFFFFFFF for w in words]
    
    return words


def bits_to_ascii(bits):
    """
    Convert bitmap to ASCII preview.
    
    Args:
        bits: 2D list bits[8][13]
    
    Returns:
        String with ASCII art representation
    """
    lines = []
    for row in bits:
        line = ''.join('#' if bit else '.' for bit in row)
        lines.append(line)
    return '\n'.join(lines)


def generate_test_pattern():
    """
    Generate test pattern: leftmost and rightmost columns ON.
    
    Returns:
        2D list bits[8][13]
    """
    bits = []
    for row in range(8):
        row_bits = []
        for col in range(13):
            # Set bit ON for leftmost (col=0) and rightmost (col=12) columns
            row_bits.append(1 if (col == 0 or col == 12) else 0)
        bits.append(row_bits)
    return bits


def run_self_test():
    """
    Run self-test with known pattern.
    
    Returns:
        True if test passes, False otherwise
    """
    print("Running self-test...")
    bits = generate_test_pattern()
    words = pack_bits_to_u32(bits)
    
    expected = [0x800C0060, 0x03001800, 0xC0060030, 0x01000000]
    
    print(f"Generated: {[hex(w) for w in words]}")
    print(f"Expected:  {[hex(w) for w in expected]}")
    print("\nPreview:")
    print(bits_to_ascii(bits))
    
    if words == expected:
        print("\n✓ SELF TEST PASS")
        return True
    else:
        print("\n✗ SELF TEST FAIL")
        return False


def pil_to_numpy(img):
    """Convert PIL image to numpy array."""
    return np.array(img)


def numpy_to_pil(arr):
    """Convert numpy array to PIL image."""
    return Image.fromarray(arr.astype(np.uint8))


def generate_edge_pulse_animation(img, args):
    """
    AI Animation: Edge detection with pulsing threshold (Canny edge detector).
    Animates by varying edge detection sensitivity.
    """
    if not HAS_CV2:
        print("Warning: opencv-python not installed. Falling back to threshold animation.")
        return generate_threshold_fallback(img, args)
    
    # Convert to grayscale and crop
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    img = img.convert('L')
    img = crop_top_bottom_to_aspect(img, 13, 8)
    
    # Get larger version for better edge detection
    img_large = img.resize((130, 80), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
    img_np = pil_to_numpy(img_large)
    
    frames_data = []
    for i in range(args.frames):
        # Vary Canny thresholds
        t = i / max(args.frames - 1, 1)
        low_thresh = int(30 + t * 100)
        high_thresh = int(low_thresh * 2.5)
        
        edges = cv2.Canny(img_np, low_thresh, high_thresh)
        edge_img = numpy_to_pil(edges)
        edge_img = edge_img.resize((13, 8), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
        
        bits = pil_to_bits(edge_img, args.threshold, args.invert)
        words = pack_bits_to_u32(bits)
        frames_data.append((words, bits))
    
    return frames_data


def generate_morph_animation(img, args):
    """
    AI Animation: Morphological operations (erosion to dilation).
    Uses mathematical morphology to create organic-looking animations.
    """
    if not HAS_SKIMAGE:
        print("Warning: scikit-image not installed. Falling back to threshold animation.")
        return generate_threshold_fallback(img, args)
    
    # Prepare base image
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    img = img.convert('L')
    img = crop_top_bottom_to_aspect(img, 13, 8)
    img = img.resize((13, 8), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
    
    img_np = pil_to_numpy(img)
    binary = img_np > args.threshold
    
    frames_data = []
    for i in range(args.frames):
        t = i / max(args.frames - 1, 1)
        
        if t < 0.5:
            # Erosion phase
            iterations = int((0.5 - t) * 4)
            if iterations > 0:
                morphed = morphology.binary_erosion(binary, morphology.disk(1))
                for _ in range(iterations - 1):
                    morphed = morphology.binary_erosion(morphed, morphology.disk(1))
            else:
                morphed = binary
        else:
            # Dilation phase
            iterations = int((t - 0.5) * 4)
            if iterations > 0:
                morphed = morphology.binary_dilation(binary, morphology.disk(1))
                for _ in range(iterations - 1):
                    morphed = morphology.binary_dilation(morphed, morphology.disk(1))
            else:
                morphed = binary

        # Convert boolean array to int and ensure proper shape
        morphed_array = morphed.astype(int)
        if args.invert:
            morphed_array = 1 - morphed_array
        
        # Convert to list of lists (8 rows, 13 cols)
        bits = morphed_array.tolist()
        words = pack_bits_to_u32(bits)
        frames_data.append((words, bits))
    
    return frames_data


def generate_contour_wave_animation(img, args):
    """
    AI Animation: Contour detection with wave effect.
    Detects object contours and animates emphasis.
    """
    if not HAS_CV2:
        print("Warning: opencv-python not installed. Falling back to threshold animation.")
        return generate_threshold_fallback(img, args)
    
    # Prepare image
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    img = img.convert('L')
    img = crop_top_bottom_to_aspect(img, 13, 8)
    
    img_large = img.resize((130, 80), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
    img_np = pil_to_numpy(img_large)
    
    # Find contours
    _, binary = cv2.threshold(img_np, args.threshold, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    frames_data = []
    for i in range(args.frames):
        canvas = np.zeros_like(img_np)
        
        # Draw contours with varying thickness
        thickness = 1 + int(3 * abs(np.sin(i * np.pi / args.frames)))
        cv2.drawContours(canvas, contours, -1, 255, thickness)
        
        # Also add filled contours with fade
        alpha = 0.3 + 0.7 * abs(np.sin(i * np.pi / args.frames))
        filled = np.zeros_like(img_np)
        cv2.drawContours(filled, contours, -1, 255, -1)
        canvas = cv2.addWeighted(canvas.astype(float), 1.0, filled.astype(float), alpha, 0)
        
        result_img = numpy_to_pil(canvas)
        result_img = result_img.resize((13, 8), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
        
        bits = pil_to_bits(result_img, 128, args.invert)
        words = pack_bits_to_u32(bits)
        frames_data.append((words, bits))
    
    return frames_data


def generate_zoom_animation(img, args):
    """
    AI Animation: Zoom in/out with center focus.
    Creates a breathing/pulsing effect.
    """
    frames_data = []
    
    for i in range(args.frames):
        # Create zoom effect
        t = i / max(args.frames - 1, 1)
        zoom_factor = 1.0 + 0.5 * np.sin(t * 2 * np.pi)  # Oscillate between 0.5x and 1.5x
        
        img_copy = img.copy()
        if img_copy.mode == 'RGBA':
            background = Image.new('RGB', img_copy.size, (255, 255, 255))
            background.paste(img_copy, mask=img_copy.split()[3])
            img_copy = background
        
        img_copy = img_copy.convert('L')
        img_copy = crop_top_bottom_to_aspect(img_copy, 13, 8)
        
        # Calculate zoom
        w, h = img_copy.size
        new_w = int(w / zoom_factor)
        new_h = int(h / zoom_factor)
        
        left = (w - new_w) // 2
        top = (h - new_h) // 2
        
        if new_w > 0 and new_h > 0:
            img_cropped = img_copy.crop((left, top, left + new_w, top + new_h))
            img_zoomed = img_cropped.resize((13, 8), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
        else:
            img_zoomed = img_copy.resize((13, 8), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
        
        bits = pil_to_bits(img_zoomed, args.threshold, args.invert)
        words = pack_bits_to_u32(bits)
        frames_data.append((words, bits))
    
    return frames_data


def generate_wave_distort_animation(img, args):
    """
    AI Animation: Wave distortion using image warping.
    Creates flowing wave effect across the image.
    """
    if not HAS_SKIMAGE:
        print("Warning: scikit-image not installed. Falling back to zoom animation.")
        return generate_zoom_animation(img, args)
    
    from scipy import ndimage
    
    # Prepare base image
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    img = img.convert('L')
    img = crop_top_bottom_to_aspect(img, 13, 8)
    img_large = img.resize((130, 80), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
    img_np = pil_to_numpy(img_large)
    
    frames_data = []
    for i in range(args.frames):
        # Create wave distortion
        t = i / max(args.frames - 1, 1) * 2 * np.pi
        
        rows, cols = img_np.shape
        row_indices, col_indices = np.meshgrid(np.arange(rows), np.arange(cols), indexing='ij')
        
        # Apply sinusoidal distortion
        wave_amplitude = 5
        row_indices = row_indices + wave_amplitude * np.sin(2 * np.pi * col_indices / cols + t)
        col_indices = col_indices + wave_amplitude * np.sin(2 * np.pi * row_indices / rows + t)
        
        # Warp image
        distorted = ndimage.map_coordinates(img_np, [row_indices, col_indices], order=1, mode='nearest')
        
        result_img = numpy_to_pil(distorted)
        result_img = result_img.resize((13, 8), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
        
        bits = pil_to_bits(result_img, args.threshold, args.invert)
        words = pack_bits_to_u32(bits)
        frames_data.append((words, bits))
    
    return frames_data


def generate_saliency_animation(img, args):
    """
    AI Animation: Saliency-based focus animation.
    Highlights visually important regions over time using edge-based saliency.
    """
    if not HAS_CV2:
        print("Warning: opencv-python not installed. Falling back to threshold animation.")
        return generate_threshold_fallback(img, args)
    
    # Prepare image
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    img = img.convert('L')
    img = crop_top_bottom_to_aspect(img, 13, 8)
    img_large = img.resize((130, 80), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
    img_np = pil_to_numpy(img_large)
    
    # Compute saliency map using Laplacian (edge-based)
    laplacian = cv2.Laplacian(img_np, cv2.CV_64F)
    saliency = np.abs(laplacian)
    saliency = (saliency / saliency.max() * 255).astype(np.uint8)
    
    frames_data = []
    for i in range(args.frames):
        t = i / max(args.frames - 1, 1)
        
        # Blend original with saliency map
        alpha = abs(np.sin(t * 2 * np.pi))
        blended = cv2.addWeighted(img_np.astype(float), 1 - alpha, saliency.astype(float), alpha, 0)
        
        result_img = numpy_to_pil(blended)
        result_img = result_img.resize((13, 8), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
        
        bits = pil_to_bits(result_img, args.threshold, args.invert)
        words = pack_bits_to_u32(bits)
        frames_data.append((words, bits))
    
    return frames_data


def generate_threshold_fallback(img, args):
    """Fallback animation when AI libraries not available."""
    frames_data = []
    thresholds = [int(32 + (i * 192 // args.frames)) for i in range(args.frames)]
    for thresh in thresholds:
        bits = image_to_13x8_bits(img.copy(), threshold=thresh, invert=args.invert,
                                  rotate=args.rotate, mirror=args.mirror, flip=args.flip)
        words = pack_bits_to_u32(bits)
        frames_data.append((words, bits))
    return frames_data


def pil_to_bits(img, threshold, invert):
    """Convert PIL image to bit matrix directly."""
    pixels = list(img.getdata())
    bits = []
    for row in range(8):
        row_bits = []
        for col in range(13):
            pixel_val = pixels[row * 13 + col]
            is_on = pixel_val < threshold if invert else pixel_val >= threshold
            row_bits.append(1 if is_on else 0)
        bits.append(row_bits)
    return bits


def write_header_file(filename, frames_data, frame_names, single_frame=False):
    """
    Write Arduino-style header file with frame data.
    
    Args:
        filename: Output filename
        frames_data: List of (words, bits) tuples
        frame_names: List of names for each frame
        single_frame: If True, write as single array; if False, write as multiple arrays
    """
    from datetime import datetime
    
    with open(filename, 'w') as f:
        # Write header comment
        f.write("/*\n")
        f.write(" * Auto-generated LED Matrix Frame Data\n")
        f.write(f" * Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(" * Format: 13x8 LED matrix packed into 4 uint32 values\n")
        f.write(" * Packing: MSB-first, row-major order\n")
        f.write(" */\n\n")
        
        # Write include guard
        guard_name = filename.upper().replace('.', '_').replace('-', '_')
        f.write(f"#ifndef {guard_name}\n")
        f.write(f"#define {guard_name}\n\n")
        
        if single_frame:
            # Write single frame
            words, bits = frames_data[0]
            frame_name = frame_names[0]
            
            f.write(f"const uint32_t {frame_name}[] = {{\n")
            for i, word in enumerate(words):
                f.write(f"    0x{word:08x}")
                if i < len(words) - 1:
                    f.write(",")
                f.write("\n")
            f.write("};\n\n")
            
            # Write ASCII preview as comment
            f.write(f"/* ASCII Preview:\n")
            for line in bits_to_ascii(bits).split('\n'):
                f.write(f" * {line}\n")
            f.write(" */\n")
        else:
            # Write multiple frames
            for idx, ((words, bits), frame_name) in enumerate(zip(frames_data, frame_names)):
                f.write(f"const uint32_t {frame_name}[] = {{\n")
                for i, word in enumerate(words):
                    f.write(f"    0x{word:08x}")
                    if i < len(words) - 1:
                        f.write(",")
                    f.write("\n")
                f.write("};\n\n")
            
            # Write frame array pointer array
            f.write("const uint32_t* const frames[] = {\n")
            for frame_name in frame_names:
                f.write(f"    {frame_name},\n")
            f.write("};\n\n")
            
            f.write(f"const int FRAME_COUNT = {len(frames_data)};\n\n")
            
            # Write ASCII previews as comments
            f.write("/* ASCII Previews:\n")
            for idx, (_, bits) in enumerate(frames_data):
                f.write(f" * Frame {idx}:\n")
                for line in bits_to_ascii(bits).split('\n'):
                    f.write(f" * {line}\n")
                f.write(" *\n")
            f.write(" */\n")
        
        # Close include guard
        f.write(f"\n#endif // {guard_name}\n")
    
    print(f"Generated header file: {filename}")


def generate_animation(img, args):
    """
    Generate animation frames using various techniques including AI-based CV.
    
    Args:
        img: PIL Image object
        args: Command line arguments
    
    Returns:
        Exit code
    """
    import time
    import os
    
    frames_data = []
    
    if args.animate == 'rotate':
        # Generate rotation frames
        angles = [i * 360 // args.frames for i in range(args.frames)]
        for angle in angles:
            bits = image_to_13x8_bits(
                img.copy(),
                threshold=args.threshold,
                invert=args.invert,
                rotate=angle,
                mirror=args.mirror,
                flip=args.flip
            )
            words = pack_bits_to_u32(bits)
            frames_data.append((words, bits))
    
    elif args.animate == 'threshold':
        # Generate threshold sweep frames
        thresholds = [int(32 + (i * 192 // args.frames)) for i in range(args.frames)]
        for thresh in thresholds:
            bits = image_to_13x8_bits(
                img.copy(),
                threshold=thresh,
                invert=args.invert,
                rotate=args.rotate,
                mirror=args.mirror,
                flip=args.flip
            )
            words = pack_bits_to_u32(bits)
            frames_data.append((words, bits))
    
    elif args.animate == 'flip':
        # Generate flip animation (original, flip, original, flip...)
        for i in range(args.frames):
            do_flip = (i % 2 == 1)
            bits = image_to_13x8_bits(
                img.copy(),
                threshold=args.threshold,
                invert=args.invert,
                rotate=args.rotate,
                mirror=args.mirror,
                flip=do_flip
            )
            words = pack_bits_to_u32(bits)
            frames_data.append((words, bits))
    
    # AI-based animation modes
    elif args.animate == 'edge-pulse':
        frames_data = generate_edge_pulse_animation(img, args)
    
    elif args.animate == 'morph':
        frames_data = generate_morph_animation(img, args)
    
    elif args.animate == 'contour-wave':
        frames_data = generate_contour_wave_animation(img, args)
    
    elif args.animate == 'zoom':
        frames_data = generate_zoom_animation(img, args)
    
    elif args.animate == 'wave-distort':
        frames_data = generate_wave_distort_animation(img, args)
    
    elif args.animate == 'saliency':
        frames_data = generate_saliency_animation(img, args)
    
    # Write to output file if specified
    if args.output:
        output_file = args.output
    else:
        output_file = 'frames.h' if args.animate else None
    
    if output_file:
        frame_names = [f"{args.frame_name}_{i}" for i in range(len(frames_data))]
        write_header_file(output_file, frames_data, frame_names, single_frame=False)
        print(f"Header file written to: {output_file}\n")
    
    # Output all frames
    if args.c_array:
        print("const uint32_t animation[][4] = {")
        for i, (words, _) in enumerate(frames_data):
            print(f"    {{ {', '.join(f'0x{w:08X}' for w in words)} }},  // Frame {i}")
        print("};")
        print(f"\nconst int FRAME_COUNT = {len(frames_data)};")
    else:
        for i, (words, bits) in enumerate(frames_data):
            print(f"\n{'='*40}")
            print(f"Frame {i}:")
            print("Words: " + " ".join(f"0x{w:08X}" for w in words))
            print("Python: [" + ", ".join(f"0x{w:08x}" for w in words) + "]")
            print("\nPreview:")
            print(bits_to_ascii(bits))
    
    # Live ASCII animation preview
    print(f"\n{'='*40}")
    print("Live Animation Preview (Ctrl+C to stop):")
    print("="*40)
    try:
        frame_idx = 0
        while True:
            _, bits = frames_data[frame_idx % len(frames_data)]
            # Clear screen (works on Windows)
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"Frame {frame_idx % len(frames_data)}/{len(frames_data)-1}")
            print(bits_to_ascii(bits))
            time.sleep(0.2)  # 5 FPS
            frame_idx += 1
    except KeyboardInterrupt:
        print("\n\nAnimation stopped.")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Convert image to 13×8 monochrome bitmap packed into 4 uint32 values'
    )
    parser.add_argument('input', nargs='?', help='Input image file (png, jpg, etc)')
    parser.add_argument('--threshold', type=int, default=128,
                        help='Grayscale threshold (0-255, default: 128)')
    parser.add_argument('--invert', action='store_true',
                        help='Invert binary output (dark becomes ON)')
    parser.add_argument('--rotate', type=int, choices=[0, 90, 180, 270], default=0,
                        help='Rotate image (degrees, default: 0)')
    parser.add_argument('--mirror', action='store_true',
                        help='Mirror horizontally (left-right)')
    parser.add_argument('--flip', action='store_true',
                        help='Flip vertically (top-bottom)')
    parser.add_argument('--c-array', action='store_true',
                        help='Output C/Arduino array format')
    parser.add_argument('--output', '-o', type=str,
                        help='Output header file (default: frames.h for animations, single frame for static)')
    parser.add_argument('--frame-name', type=str, default='frame',
                        help='Name for the frame array in header file (default: frame)')
    parser.add_argument('--self-test', action='store_true',
                        help='Run self-test with known pattern')
    parser.add_argument('--animate', type=str, 
                        choices=['rotate', 'threshold', 'flip', 'edge-pulse', 'morph', 
                                'contour-wave', 'zoom', 'wave-distort', 'saliency'],
                        help='Generate animation frames (AI modes: edge-pulse, morph, contour-wave, zoom, wave-distort, saliency)')
    parser.add_argument('--frames', type=int, default=8,
                        help='Number of animation frames (default: 8)')
    
    args = parser.parse_args()
    
    # Handle self-test mode
    if args.self_test:
        success = run_self_test()
        return 0 if success else 1
    
    # Require input file if not in self-test mode
    if not args.input:
        parser.error("input file is required (or use --self-test)")
    
    try:
        # Load image
        img = Image.open(args.input)
        
        # Handle animation mode
        if args.animate:
            return generate_animation(img, args)
        
        # Convert to bitmap
        bits = image_to_13x8_bits(
            img,
            threshold=args.threshold,
            invert=args.invert,
            rotate=args.rotate,
            mirror=args.mirror,
            flip=args.flip
        )
        
        # Pack into uint32 values
        words = pack_bits_to_u32(bits)
        
        # Output results
        print("Words: " + " ".join(f"0x{w:08X}" for w in words))
        print("Python: [" + ", ".join(f"0x{w:08x}" for w in words) + "]")
        
        if args.c_array:
            c_array = "const uint32_t frame[4] = { " + ", ".join(f"0x{w:08X}" for w in words) + " };"
            print("C-Array: " + c_array)
        
        print("\nPreview:")
        print(bits_to_ascii(bits))
        
        # Write to output file if specified
        if args.output:
            write_header_file(args.output, [(words, bits)], [args.frame_name], single_frame=True)
            print(f"\nHeader file written to: {args.output}")
        
        return 0
        
    except FileNotFoundError:
        print(f"Error: File '{args.input}' not found", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
