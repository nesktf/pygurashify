from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union
from pathlib import Path

import math
import numpy as np
from PIL import Image


class EdgeMethod(Enum):
    SOBEL = 0
    PREWITT = 1
    LAPLACIAN = 2
    ROBERTS = 3


class AspectMode(Enum):
    ASPECT_ORIGINAL = 0
    ASPECT_4_3 = 1
    ASPECT_16_9 = 2
    ASPECT_1_1 = 3


@dataclass(frozen=True)
class EdgeOpts:
    method: EdgeMethod = EdgeMethod.SOBEL
    threshold: float = 80.0  # [0.0, 255.0]
    opacity: float = 0.5  # [0.0, 1.0]
    invert: bool = False  # use white edges on black background


@dataclass(frozen=True)
class BlurOpts:
    radius: int = 9  # in pixels, [0, 30]
    angle: float = -25.0  # in degrees, [-90.0, 90.0]
    opacity: float = 0.7  # for alpha blending [0.0, 1.0]


@dataclass(frozen=True)
class ProcessOpts:
    aspect_mode: AspectMode = AspectMode.ASPECT_ORIGINAL
    max_height: Optional[int] = 1080  # for downscaling
    white_level: Optional[float] = 85.0  # (50.0, 100.0]
    unsharpening: Optional[float] = 1.0  # [0.0, 3.0]
    posterize_levels: Optional[int] = 9  # quantization steps, [2, 20]
    blur: Optional[BlurOpts] = BlurOpts()
    edges: Optional[EdgeOpts] = EdgeOpts()


def clamp(val, min_val, max_val):
    return max(min_val, min(val, max_val))


def clamp_array(arr: np.ndarray) -> np.ndarray:
    return np.clip(arr, 0.0, 255.0)


def directional_box_blur(src: np.ndarray, radius: int, angle: float) -> np.ndarray:
    h, w = src.shape[:2]
    rad = max(1, int(radius))
    ang = math.radians(angle)
    dx = math.cos(ang)
    dy = math.sin(ang)
    accum = np.zeros_like(src, dtype=np.float64)
    count = np.zeros((h, w) + (1,) * (src.ndim - 2), dtype=np.float64)
    for k in range(-rad, rad + 1):
        shift_x = int(round(k * dx))
        shift_y = int(round(k * dy))

        src_y_start = max(0, shift_y)
        src_y_end = min(h, h + shift_y)
        src_x_start = max(0, shift_x)
        src_x_end = min(w, w + shift_x)

        dst_y_start = max(0, -shift_y)
        dst_y_end = min(h, h - shift_y)
        dst_x_start = max(0, -shift_x)
        dst_x_end = min(w, w - shift_x)

        accum[dst_y_start:dst_y_end, dst_x_start:dst_x_end] += src[
            src_y_start:src_y_end, src_x_start:src_x_end
        ]
        count[dst_y_start:dst_y_end, dst_x_start:dst_x_end] += 1.0

    return accum / np.maximum(count, 1.0)


def apply_level_adjustment(arr: np.ndarray, white_level: float) -> np.ndarray:
    black_level = 100.0 - white_level
    b = (black_level / 100.0) * 255.0
    w = (white_level / 100.0) * 255.0
    s = 255.0 / (w - b)
    return clamp_array((arr - b) * s)


def apply_unsharp(arr: np.ndarray, unsharp_amount: float) -> np.ndarray:
    blur = directional_box_blur(arr, radius=2, angle=0.0)
    return clamp_array(arr + unsharp_amount * (arr - blur))


def apply_blur(arr: np.ndarray, blur_opts: BlurOpts) -> np.ndarray:
    radius = clamp(blur_opts.radius, 0, 30)
    angle = clamp(blur_opts.angle, -90.0, 90.0)
    opacity = clamp(blur_opts.opacity, 0.0, 1.0)
    blur = directional_box_blur(arr.copy(), radius, angle)
    return clamp_array(arr * (1.0 - opacity) + blur * opacity)  # blend blur + image


def apply_posterization(arr: np.ndarray, levels: int) -> np.ndarray:
    # simple color quantization
    step = 255.0 / (levels - 1)
    return np.round(arr / step) * step


def apply_edges(orig: np.ndarray, base: np.ndarray, edge_opts: EdgeOpts) -> np.ndarray:
    def detect_edges(gray: np.ndarray, method: EdgeMethod) -> np.ndarray:
        h, w = gray.shape
        out = np.zeros((h, w), dtype=np.float64)

        if method == EdgeMethod.ROBERTS:
            # Roberts cross 2x2
            gx = gray[:-1, :-1] - gray[1:, 1:]
            gy = gray[:-1, 1:] - gray[1:, :-1]
            out[:-1, :-1] = np.sqrt(gx * gx + gy * gy)
            return out

        # 3x3 kernels (interior coordinates 1 to h-1, 1 to w-1)
        p00 = gray[0:-2, 0:-2]
        p01 = gray[0:-2, 1:-1]
        p02 = gray[0:-2, 2:]
        p10 = gray[1:-1, 0:-2]
        p11 = gray[1:-1, 1:-1]
        p12 = gray[1:-1, 2:]
        p20 = gray[2:, 0:-2]
        p21 = gray[2:, 1:-1]
        p22 = gray[2:, 2:]

        if method == EdgeMethod.PREWITT:
            gx = -p00 + p02 - p10 + p12 - p20 + p22
            gy = -p00 - p01 - p02 + p20 + p21 + p22
            out[1:-1, 1:-1] = np.sqrt(gx * gx + gy * gy)
        elif method == EdgeMethod.LAPLACIAN:
            sum_k = p01 + p10 - 4.0 * p11 + p12 + p21
            out[1:-1, 1:-1] = np.abs(sum_k)
        else:  # EdgeMethod.SOBEL
            gx = -p00 + p02 - 2.0 * p10 + 2.0 * p12 - p20 + p22
            gy = -p00 - 2.0 * p01 - p02 + p20 + 2.0 * p21 + p22
            out[1:-1, 1:-1] = np.sqrt(gx * gx + gy * gy)

        return out

    def apply_multiply_blend(blend: np.ndarray, opacity: float) -> np.ndarray:
        b = base / 255.0
        if blend.ndim == 2:
            blend = blend[..., np.newaxis]
        l = blend / 255.0
        result = 255.0 * (b * (1.0 - opacity) + b * l * opacity)
        return clamp_array(result)

    gray = orig[..., 0] * 0.30 + orig[..., 1] * 0.59 + orig[..., 2] * 0.11
    edge = detect_edges(gray, method=edge_opts.method)

    threshold = clamp(edge_opts.threshold, 0, 255)
    edge_mask = np.where(edge > threshold, 255.0, 0.0)
    if not edge_opts.invert:
        edge_mask = 255.0 - edge_mask

    opacity = clamp(edge_opts.opacity, 0.0, 1.0)
    return apply_multiply_blend(edge_mask, opacity)


def process_array(pixels: np.ndarray, opts: ProcessOpts) -> np.ndarray:
    """Apply the Higurashi image filter pipeline to an RGB float array (0..255)"""
    orig = pixels.astype(np.float64).copy()
    base = orig.copy()
    if opts.white_level:
        base = apply_level_adjustment(base, clamp(opts.white_level, 50.1, 100.0))
    if opts.unsharpening:
        base = apply_unsharp(base, clamp(opts.unsharpening, 0.0, 3.0))
    if opts.blur:
        base = apply_blur(base, opts.blur)
    if opts.posterize_levels:
        base = apply_posterization(base, clamp(opts.posterize_levels, 2, 20))
    if opts.edges:
        base = apply_edges(orig, base, opts.edges)
    return np.uint8(clamp_array(base))


def preprocess_image(
    img: Image.Image, aspect_mode: AspectMode, max_height: Optional[int]
) -> Image.Image:
    src_w, src_h = img.size
    crop_w, crop_h = src_w, src_h
    if aspect_mode != AspectMode.ASPECT_ORIGINAL:
        ratios = {
            AspectMode.ASPECT_4_3: 4.0 / 3.0,
            AspectMode.ASPECT_16_9: 16.0 / 9.0,
            AspectMode.ASPECT_1_1: 1.0,
        }

        target = ratios.get(aspect_mode)
        if src_w / src_h > target:
            crop_w = int(round(src_h * target))
            crop_h = src_h
        elif src_w / src_h < target:
            crop_w = src_w
            crop_h = int(round(src_w / target))

        crop_x = (src_w - crop_w) // 2
        crop_y = (src_h - crop_h) // 2
        img = img.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))

    if max_height and max_height > 0 and img.height > max_height:
        scale = max_height / img.height
        new_w = int(round(img.width * scale))
        img = img.resize((new_w, max_height), Image.Resampling.LANCZOS)

    return img


def process_image(
    input_path: Union[str, Path], output_path: Union[str, Path], opts: ProcessOpts
):
    """Loads image from `input_path`, applies the filter pipeline, and saves to `output_path`"""
    with Image.open(input_path) as img:
        img = preprocess_image(img.convert("RGB"), opts.aspect_mode, opts.max_height)
        pixels = np.array(img, dtype=np.float64)

    processed = Image.fromarray(process_array(pixels, opts), mode="RGB")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    processed.save(out)
