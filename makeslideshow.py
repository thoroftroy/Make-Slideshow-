#!/usr/bin/env python3
"""
Batch slideshow generator — one MP4 per subdirectory.

Point it at a folder containing subdirectories full of images.
Each subdirectory becomes its own slideshow video saved to
~/Videos/SlideshowClips/ (created automatically if needed).

- 4.5 s per image, 0.5 s transitions, 30 fps, 1080p
- transitions are randomised but never repeat back-to-back
- images are centred with black bars — no cropping, no stretching
- only .jpg / .jpeg / .png files are used

Usage:
  makeslideshow ~/photos/funeral/
  → ~/Videos/SlideshowClips/childhood.mp4  wedding.mp4  service.mp4

Requires: ffmpeg >= 4.3  (with xfade filter)
"""

import argparse
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ── dynamic transitions  (grouped by style, no boring fades) ─────────────────
TRANSITIONS = [
    # wipes — directional erases
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "wipetl", "wipetr", "wipebl", "wipebr",
    # slides — push the frame
    "slideleft", "slideright", "slideup", "slidedown",
    "smoothleft", "smoothright", "smoothup", "smoothdown",
    # covers / reveals — one image moves over / under the other
    "coverleft", "coverright", "coverup", "coverdown",
    "revealleft", "revealright", "revealup", "revealdown",
    # diagonals
    "diagtl", "diagtr", "diagbl", "diagbr",
    # slices — bands sweep in from the edge
    "hlslice", "hrslice", "vuslice", "vdslice",
    # wind — blurred push from edge
    "hlwind", "hrwind", "vuwind", "vdwind",
    # open / close — mattes that shrink or expand
    "horzopen", "horzclose", "vertopen", "vertclose",
    "circleopen", "circleclose",
    # crop / geometry — shapes grow / shrink
    "circlecrop", "rectcrop",
    "radial",
    # squeeze — compress out / in
    "squeezeh", "squeezev",
    # zoom / blur / pixelate / dissolve
    "zoomin",
    "hblur",
    "pixelize", "dissolve",
    "fadegrays", "distance",
]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def natkey(s):
    """Natural sort key: splits string into text / int chunks so 10 > 2."""
    return [
        int(t) if t.isdigit() else t.lower()
        for t in re.split(r"(\d+)", s)
    ]


# ── helpers ──────────────────────────────────────────────────────────────────

def get_images(directory):
    p = Path(directory)
    if not p.is_dir():
        return []
    return sorted(
        (str(f) for f in p.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda p: natkey(os.path.basename(p)),
    )


def get_subdirs(parent):
    """Return sorted immediate subdirectories of *parent*."""
    p = Path(parent)
    if not p.is_dir():
        return []
    return sorted(
        str(d) for d in p.iterdir() if d.is_dir()
    )


def run(cmd, label=""):
    if label:
        print(f"  {label}")
    subprocess.run(cmd, check=True)


def pick_transition(pool, last):
    """Pick a random transition that differs from *last*."""
    candidates = [t for t in pool if t != last]
    if not candidates:
        candidates = list(pool)
    return random.choice(candidates)


def build_slideshow(images, output, img_dur, trans_dur, transitions,
                    width, height, fps, crf, preset):
    n = len(images)
    if n == 0:
        return False

    # centre-fit with black bars (never crop, never stretch)
    fit = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
           f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2")

    # ── single image ─────────────────────────────────────────────────────────
    if n == 1:
        cmd = [
            "ffmpeg", "-y", "-hide_banner",
            "-loop", "1", "-i", images[0],
            "-t", str(img_dur),
            "-vf", f"{fit},setsar=1,fps={fps},format=yuv420p",
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            output,
        ]
        run(cmd, f"1 image")
        return True

    # ── multiple images: chain with xfade ─────────────────────────────────────
    total_dur = n * img_dur + (n - 1) * trans_dur

    inputs = []
    for i in range(n):
        if i == 0 or i == n - 1:
            need = img_dur + trans_dur          # 5.0 s
        else:
            need = img_dur + 2 * trans_dur      # 5.5 s
        inputs.extend(["-loop", "1", "-t", str(need), "-i", images[i]])

    parts = []

    # scale / pad / fps-normalise
    for i in range(n):
        parts.append(
            f"[{i}:v]{fit},"
            f"setsar=1,fps={fps},setpts=PTS-STARTPTS[v{i}];"
        )

    # xfade chain with no consecutive repeats
    cur = "v0"
    last = None
    for i in range(1, n):
        t = pick_transition(transitions, last)
        last = t
        offset = i * img_dur + (i - 1) * trans_dur
        nxt = f"x{i}"
        parts.append(
            f"[{cur}][v{i}]"
            f"xfade=transition={t}:duration={trans_dur}:offset={offset}"
            f"[{nxt}];"
        )
        cur = nxt

    parts.append(f"[{cur}]format=yuv420p[out]")
    filter_str = "".join(parts)

    cmd = [
        "ffmpeg", "-y", "-hide_banner",
        *inputs,
        "-filter_complex", filter_str,
        "-map", "[out]",
        "-t", str(total_dur),
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        output,
    ]
    run(cmd, f"{n} images, {n-1} transitions")
    return True


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Create a slideshow MP4 for each subdirectory of IMAGE_DIR"
    )
    parser.add_argument(
        "image_dir", nargs="?", default=None,
        help="Parent folder — each subdirectory becomes its own slideshow  [default: current directory]",
    )
    parser.add_argument(
        "-d", "--duration", type=float, default=4.5,
        help="Seconds each image is fully displayed  [default: 4.5]",
    )
    parser.add_argument(
        "-t", "--transition", type=float, default=0.5,
        help="Transition duration in seconds  [default: 0.5]",
    )
    parser.add_argument(
        "-W", "--width", type=int, default=1920,
        help="Output width  [default: 1920]",
    )
    parser.add_argument(
        "-H", "--height", type=int, default=1080,
        help="Output height  [default: 1080]",
    )
    parser.add_argument(
        "--fps", type=int, default=30,
        help="Frames per second  [default: 30]",
    )
    parser.add_argument(
        "--crf", type=int, default=18,
        help="Quality — lower is better, 18–28 typical  [default: 18]",
    )
    parser.add_argument(
        "--preset", default="medium",
        choices=[
            "ultrafast", "superfast", "veryfast", "faster", "fast",
            "medium", "slow", "slower", "veryslow",
        ],
        help="Encoding speed vs quality  [default: medium]",
    )
    parser.add_argument(
        "-s", "--seed", type=int,
        help="Random seed for reproducible transition choices",
    )
    parser.add_argument(
        "--transitions", default=None,
        help="Comma-separated list of xfade transitions to pick from",
    )
    parser.add_argument(
        "--same-transition",
        help="Use a single transition for every cut  (e.g. wipeleft)",
    )
    parser.add_argument(
        "--keep-temp", action="store_true",
        help="Keep temporary intermediate files",
    )
    parser.add_argument(
        "--temp-dir",
        help="Directory for temporary files  (default: system temp)",
    )
    parser.add_argument(
        "--list-transitions", action="store_true",
        help="Print available transitions and exit",
    )

    args = parser.parse_args()

    if args.list_transitions:
        print("Available xfade transitions:")
        for t in TRANSITIONS:
            print(f"  {t}")
        sys.exit(0)

    if args.same_transition:
        chosen = [args.same_transition]
    elif args.transitions:
        chosen = [t.strip() for t in args.transitions.split(",") if t.strip()]
    else:
        chosen = list(TRANSITIONS)

    if args.seed is not None:
        random.seed(args.seed)

    # default to current directory if none given
    root = args.image_dir or os.getcwd()

    # discover subdirectories
    subdirs = get_subdirs(root)
    if not subdirs:
        print(f"No subdirectories found in {root}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(subdirs)} subdirector{'y' if len(subdirs) == 1 else 'ies'} "
          f"in {root}\n")

    # output goes into ~/Videos/SlideshowClips/
    out_dir = os.path.expanduser("~/Videos/SlideshowClips")
    os.makedirs(out_dir, exist_ok=True)

    temp_dir = args.temp_dir or tempfile.mkdtemp(prefix="slideshow_")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        done = 0
        skipped = 0

        for idx, subdir in enumerate(subdirs):
            images = get_images(subdir)
            if not images:
                print(f"[SKIP]  {subdir}  — no images")
                skipped += 1
                continue

            dir_name = os.path.basename(os.path.normpath(subdir))
            out_path = os.path.join(out_dir, f"{dir_name}.mp4")

            print(f"[{idx+1}/{len(subdirs)}]  {dir_name}  ({len(images)} images)")

            seg = os.path.join(temp_dir, f"build_{idx:04d}.mp4")
            ok = build_slideshow(
                images, seg, args.duration, args.transition, chosen,
                args.width, args.height, args.fps, args.crf, args.preset,
            )
            if not ok:
                skipped += 1
                continue

            shutil.move(seg, out_path)
            done += 1
            print(f"  →  {out_path}\n")

        print(f"\nDone — {done} clip(s) saved to {out_dir}/"
              + (f"  ({skipped} skipped)" if skipped else ""))

    finally:
        if not args.keep_temp:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
