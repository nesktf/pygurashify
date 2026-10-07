#!/usr/bin/env python3
from higurashifier import (
    AspectMode,
    BlurOpts,
    EdgeOpts,
    EdgeMethod,
    ProcessOpts,
    process_image,
)
from argparse import ArgumentParser
from typing import Optional


def parse_aspect_mode(mode: str) -> AspectMode:
    if mode == "4:3":
        return AspectMode.ASPECT_4_3
    elif mode == "16:9":
        return AspectMode.ASPECT_16_9
    elif mode == "1:1":
        return AspectMode.ASPECT_1_1
    else:
        return AspectMode.ASPECT_ORIGINAL


def main():
    parser = ArgumentParser(description="Higurashi-style image processor")
    parser.add_argument("input", help="Path to input image")
    parser.add_argument("output", help="Path to output image")

    # preprocessing
    parser.add_argument(
        "--aspect",
        choices=["original", "4:3", "16:9", "1:1"],
        default="original",
        help="Aspect ratio cropping (default: original)",
    )
    parser.add_argument(
        "--max-height",
        type=int,
        default=None,
        help="Max image height",
    )

    # contrast
    parser.add_argument(
        "--contrast-level",
        type=float,
        default=85.0,
        help="White contrast level (default: 85.0)",
    )
    parser.add_argument(
        "--no-contrast", action="store_true", help="Disable contrast filter"
    )

    # blur
    parser.add_argument(
        "--blur-angle",
        type=float,
        default=-25.0,
        help="Blur angle in degrees (default: -25.0)",
    )
    parser.add_argument(
        "--blur-opacity", type=float, default=0.7, help="Blur opacity (default: 0.7)"
    )
    parser.add_argument(
        "--blur-radius",
        type=int,
        default=9,
        help="Blur radius in pixels (default: 9)",
    )
    parser.add_argument("--no-blur", action="store_true", help="Disable blur filter")

    # edge detection
    parser.add_argument(
        "--edge-method",
        choices=["sobel", "prewitt", "laplacian", "roberts"],
        default="sobel",
        help="Edge detection algorithm (default: sobel)",
    )
    parser.add_argument(
        "--edge-threshold",
        type=float,
        default=80.0,
        help="Edge detection threshold 0-255 (default: 80.0)",
    )
    parser.add_argument(
        "--edge-opacity", type=float, default=0.5, help="Edge opacity (default: 0.5)"
    )
    parser.add_argument("--invert-edges", action="store_true", help="Invert edge color")
    parser.add_argument(
        "--no-edges", action="store_true", help="Disable edge detection"
    )

    # unsharpening
    parser.add_argument(
        "--unsharpening",
        type=float,
        default=1.0,
        help="Unsharpening mask value (default: 1.0)",
    )
    parser.add_argument(
        "--no-unsharp", action="store_true", help="Disable unsharp mask"
    )

    # posterization
    parser.add_argument(
        "--quantization", type=int, default=9, help="Quantization steps (default: 9)"
    )
    parser.add_argument(
        "--no-quantization", action="store_true", help="Disable quantization"
    )

    args = parser.parse_args()

    def make_blur_opts() -> Optional[BlurOpts]:
        if args.no_blur:
            return None
        return BlurOpts(
            radius=args.blur_radius,
            angle=args.blur_angle,
            opacity=args.blur_opacity,
        )

    def make_edge_opts() -> Optional[EdgeOpts]:
        if args.no_edges:
            return None

        def parse_edge_method(method: str) -> EdgeMethod:
            m = method.lower()
            if m == "prewitt":
                return EdgeMethod.PREWITT
            elif m == "roberts":
                return EdgeMethod.ROBERTS
            elif m == "laplacian":
                return EdgeMethod.LAPLACIAN
            else:
                return EdgeMethod.SOBEL

        return EdgeOpts(
            method=parse_edge_method(args.edge_method),
            threshold=args.edge_threshold,
            opacity=args.edge_opacity,
            invert=args.invert_edges,
        )

    opts = ProcessOpts(
        aspect_mode=parse_aspect_mode(args.aspect),
        max_height=args.max_height,
        white_level=(args.contrast_level if not args.no_contrast else None),
        unsharpening=(args.unsharpening if not args.no_unsharp else None),
        posterize_levels=(args.quantization if not args.no_quantization else None),
        blur=make_blur_opts(),
        edges=make_edge_opts(),
    )

    process_image(args.input, args.output, opts)
    print(f"Processed {args.input} -> {args.output}")


if __name__ == "__main__":
    main()
