"""
run_reconstruction.py — Charbagh Collective, PMW × TechRealm
=============================================================
Full COLMAP SfM + MVS pipeline for Shalimar Gardens, Lahore.

Project root : C:\\Users\\DELL\\OneDrive\\Desktop\\New folder
Input images : .\\images\\  (logo.png excluded)
Output PLY   : .\\output\\shalimar_gardens_reconstruction.ply

Pipeline stages:
  1. feature_extractor   (SIFT, CPU)
  2. exhaustive_matcher  (CPU)
  3. mapper              (sparse SfM)
  4. image_undistorter
  5. patch_match_stereo  (CPU)
  6. stereo_fusion       → fused.ply
  7. Copy + validate PLY
  8. Print summary table
"""

import os, sys, time, shutil, subprocess, re, glob

# ── Project paths ──────────────────────────────────────────────────────────
ROOT        = r"C:\Users\DELL\OneDrive\Desktop\New folder"
IMAGES_DIR  = os.path.join(ROOT, "images")
WORKSPACE   = os.path.join(ROOT, "workspace")
OUTPUT_DIR  = os.path.join(ROOT, "output")
OUTPUT_PLY  = os.path.join(OUTPUT_DIR, "shalimar_gardens_reconstruction.ply")
DATABASE    = os.path.join(WORKSPACE, "database.db")
SPARSE_DIR  = os.path.join(WORKSPACE, "sparse")
DENSE_DIR   = os.path.join(WORKSPACE, "dense")
FUSED_PLY   = os.path.join(DENSE_DIR, "fused.ply")

EXCLUDED = {"logo.png", "Logo.png", "logo.PNG"}
IMG_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}

# ── Helpers ────────────────────────────────────────────────────────────────

def banner(msg: str):
    print(f"\n{'═'*65}")
    print(f"  {msg}")
    print(f"{'═'*65}")


def run_step(cmd: list[str], label: str) -> float:
    """Run a COLMAP command; exit on non-zero return code."""
    print(f"\n{'─'*65}")
    print(f"  ▶ {label}")
    print(f"  $ {' '.join(cmd)}")
    print(f"{'─'*65}")
    t0 = time.time()
    result = subprocess.run(cmd, text=True)
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"\n[ERROR] Step '{label}' failed (exit code {result.returncode}).")
        sys.exit(result.returncode)
    print(f"  ✓ Completed in {elapsed:.1f}s")
    return elapsed


def find_colmap() -> str:
    """Locate the colmap executable; try PATH then common Windows install dirs."""
    candidates = [
        r"C:\Users\DELL\Downloads\colmap-x64-windows-nocuda\bin\colmap.exe",
        "colmap",
        r"C:\Users\DELL\Downloads\colmap-x64-windows-nocuda\COLMAP.bat",
        r"C:\Program Files\COLMAP\colmap.bat",
        r"C:\Program Files\COLMAP\COLMAP.bat",
        r"C:\COLMAP\colmap.bat",
        r"C:\COLMAP\COLMAP.bat",
    ]
    for exe in candidates:
        try:
            r = subprocess.run(
                [exe, "--version"], capture_output=True, text=True, timeout=10
            )
            out = (r.stdout + r.stderr)
            if "COLMAP" in out or r.returncode == 0:
                ver_line = out.strip().splitlines()[0] if out.strip() else "unknown version"
                print(f"  ✓ COLMAP found  : {ver_line}")
                print(f"    Executable    : {exe}")
                return exe
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    print("[ERROR] COLMAP is not installed or not on PATH.")
    print("  → Download from: https://colmap.github.io/install.html")
    print("  → Or run: python -m pip install pycolmap")
    sys.exit(1)


def collect_images() -> list[str]:
    """Return sorted list of input image paths, excluding logo.png."""
    imgs = []
    for f in sorted(os.listdir(IMAGES_DIR)):
        if f in EXCLUDED or f.lower() in {e.lower() for e in EXCLUDED}:
            print(f"  [EXCL] {f} — excluded from reconstruction")
            continue
        if os.path.splitext(f)[1].lower() in IMG_EXTS:
            imgs.append(os.path.join(IMAGES_DIR, f))
    return imgs


def convert_model_to_txt(colmap: str, model_dir: str) -> str:
    """Convert binary COLMAP model to TXT; return path to txt dir."""
    txt_dir = model_dir + "_txt"
    os.makedirs(txt_dir, exist_ok=True)
    subprocess.run(
        [colmap, "model_converter",
         "--input_path",  model_dir,
         "--output_path", txt_dir,
         "--output_type", "TXT"],
        capture_output=True
    )
    return txt_dir


def parse_model_stats(sparse_dir: str, colmap: str) -> tuple[int, int]:
    """Return (num_registered_images, num_sparse_3d_points)."""
    model_0 = os.path.join(sparse_dir, "0")
    if not os.path.isdir(model_0):
        print("  [WARN] No sparse model/0 found — COLMAP may not have registered any images.")
        return 0, 0

    txt_dir = convert_model_to_txt(colmap, model_0)

    images_txt  = os.path.join(txt_dir, "images.txt")
    points_txt  = os.path.join(txt_dir, "points3D.txt")
    cameras_txt = os.path.join(txt_dir, "cameras.txt")

    # images.txt: 2 lines per image (header + keypoints); count header lines
    n_imgs = 0
    if os.path.exists(images_txt):
        with open(images_txt) as f:
            lines = [l for l in f if l.strip() and not l.startswith("#")]
        n_imgs = len(lines) // 2

    # points3D.txt: 1 line per 3D point
    n_pts = 0
    if os.path.exists(points_txt):
        with open(points_txt) as f:
            n_pts = sum(1 for l in f if l.strip() and not l.startswith("#"))

    return n_imgs, n_pts


def count_ply_vertices(ply_path: str) -> int:
    """Parse PLY header to extract vertex count."""
    if not os.path.exists(ply_path):
        return 0
    header = b""
    with open(ply_path, "rb") as f:
        while b"end_header" not in header:
            chunk = f.read(512)
            if not chunk: break
            header += chunk
    m = re.search(r"element vertex\s+(\d+)", header.decode("ascii", errors="ignore"))
    return int(m.group(1)) if m else 0


def fmt_time(s: float) -> str:
    m = int(s // 60); sec = s % 60
    return f"{m}m {sec:.0f}s" if m else f"{sec:.1f}s"


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    t_total = time.time()

    banner("Charbagh Collective — Shalimar Gardens 3D Reconstruction\n"
           "  PMW × TechRealm | Heritage Preservation, Lahore")

    # ── Pre-flight ─────────────────────────────────────────────────────
    print("\n[PRE-FLIGHT CHECKS]")
    colmap = find_colmap()

    for d in [WORKSPACE, SPARSE_DIR, DENSE_DIR, OUTPUT_DIR]:
        os.makedirs(d, exist_ok=True)

    images = collect_images()
    n_input = len(images)
    print(f"  Input images  : {n_input}  (from {IMAGES_DIR})")

    if n_input < 3:
        print(f"\n[ERROR] Need ≥ 3 images; only {n_input} found in {IMAGES_DIR}.")
        print("  Run download_images.py first.")
        sys.exit(1)

    # ── Step 1 : Feature Extraction ────────────────────────────────────
    db_size = os.path.getsize(DATABASE) if os.path.exists(DATABASE) else 0
    if db_size > 1_000_000:  # DB already has features
        print(f"\n  [SKIP] Feature extraction already done (database.db = {db_size//1024//1024} MB)")
    else:
        run_step(
            [colmap, "feature_extractor",
             "--database_path",                      DATABASE,
             "--image_path",                         IMAGES_DIR,
             "--ImageReader.single_camera",          "0",
             "--ImageReader.camera_model",           "RADIAL",
             "--FeatureExtraction.use_gpu",          "0",
             "--FeatureExtraction.num_threads",      "2",   # prevents crash on Windows
             "--SiftExtraction.max_num_features",    "4096",
             "--SiftExtraction.first_octave",        "0",
            ],
            "1/6  Feature Extraction (SIFT, CPU)"
        )

    # ── Step 2 : Exhaustive Matching ───────────────────────────────────
    run_step(
        [colmap, "exhaustive_matcher",
         "--database_path",              DATABASE,
        "--FeatureMatching.use_gpu",     "0",   # CPU mode (COLMAP 4.x)
   "--SiftMatching.max_ratio", "0.95",
    "--SiftMatching.max_distance", "0.9",
    "--TwoViewGeometry.min_num_inliers", "8",
],
        "2/6  Exhaustive Feature Matching (CPU)"
    )

    # ── Step 3 : Sparse Reconstruction ────────────────────────────────
    run_step(
        [colmap, "mapper",
         "--database_path",         DATABASE,
         "--image_path",            IMAGES_DIR,
         "--output_path",           SPARSE_DIR,
         "--Mapper.num_threads",    "4",
        "--Mapper.init_min_num_inliers", "8",
    "--Mapper.abs_pose_min_num_inliers", "8",
],
        "3/6  Sparse Reconstruction (Structure-from-Motion Mapper)"
    )

    n_registered, n_sparse_pts = parse_model_stats(SPARSE_DIR, colmap)
    print(f"\n  Registered cameras : {n_registered}")
    print(f"  Sparse 3D points   : {n_sparse_pts:,}")

    if n_registered == 0:
        print("\n[ERROR] No cameras registered. The images may not have enough overlap.")
        print("  Tips: ensure images share scene content, are not too blurry,")
        print("        and try adding more images with better coverage.")
        sys.exit(1)

    model_0 = os.path.join(SPARSE_DIR, "0")

    # ── Step 4 : Image Undistortion ────────────────────────────────────
    run_step(
        [colmap, "image_undistorter",
         "--image_path",   IMAGES_DIR,
         "--input_path",   model_0,
         "--output_path",  DENSE_DIR,
         "--output_type",  "COLMAP",
         "--max_image_size", "2000",
        ],
        "4/6  Image Undistortion"
    )

    # ── Step 5 : Patch-Match Stereo (CPU) ─────────────────────────────
    run_step(
        [colmap, "patch_match_stereo",
         "--workspace_path",                      DENSE_DIR,
         "--workspace_format",                    "COLMAP",
         "--PatchMatchStereo.gpu_index",          "-1",   # CPU mode
         "--PatchMatchStereo.window_radius",      "5",
         "--PatchMatchStereo.num_iterations",     "3",
         "--PatchMatchStereo.geom_consistency",   "false",
        ],
        "5/6  Patch-Match Stereo — CPU depth estimation (may take several minutes)"
    )

    # ── Step 6 : Stereo Fusion ─────────────────────────────────────────
    run_step(
        [colmap, "stereo_fusion",
         "--workspace_path",   DENSE_DIR,
         "--workspace_format", "COLMAP",
         "--input_type",       "geometric",
         "--output_path",      FUSED_PLY,
        ],
        "6/6  Stereo Fusion → Dense PLY Point Cloud"
    )

    # ── Export & Validate ──────────────────────────────────────────────
    if not os.path.exists(FUSED_PLY):
        print(f"\n[ERROR] Expected fused PLY at {FUSED_PLY} — not found.")
        sys.exit(1)

    shutil.copy2(FUSED_PLY, OUTPUT_PLY)
    n_dense = count_ply_vertices(OUTPUT_PLY)

    if n_dense == 0:
        print("[ERROR] PLY vertex count = 0. Dense reconstruction may have failed.")
        sys.exit(1)

    t_elapsed = time.time() - t_total

    # ── Summary ────────────────────────────────────────────────────────
    print("\n\n")
    w = 63
    def row(label, value):
        print(f"║  {label:<35} {str(value):<{w-38}} ║")

    print("╔" + "═"*w + "╗")
    print("║" + "  RECONSTRUCTION SUMMARY".center(w) + "║")
    print("║" + "  Charbagh Collective | PMW × TechRealm".center(w) + "║")
    print("║" + "  Shalimar Gardens, Lahore".center(w) + "║")
    print("╠" + "═"*w + "╣")
    row("Images in ./images (input)",  n_input)
    row("Cameras registered by COLMAP", n_registered)
    row("Sparse 3D points",            f"{n_sparse_pts:,}")
    row("Dense point cloud vertices",  f"{n_dense:,}")
    row("Output PLY",                  "output\\shalimar_gardens_reconstruction.ply")
    row("Total runtime",               fmt_time(t_elapsed))
    print("╠" + "═"*w + "╣")
    print("║" + "  ✓ PLY validated — vertex count > 0".center(w) + "║")
    print("║" + "  ✓ Open with: MeshLab / CloudCompare / Three.js".center(w) + "║")
    print("╚" + "═"*w + "╝")
    print()


if __name__ == "__main__":
    main()
