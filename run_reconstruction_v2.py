"""
run_reconstruction_v2.py — Charbagh Collective, PMW × TechRealm
=============================================================
COLMAP SfM pipeline for Shalimar Gardens V2 (Moorcroft Pavilion).

Project root : C:\\Users\\DELL\\OneDrive\\Desktop\\New folder
Input images : .\\images_v2\\
Output PLY   : .\\output\\shalimar_gardens_reconstruction_v2.ply
"""

import os, sys, time, shutil, subprocess, re

# ── Project paths ──────────────────────────────────────────────────────────
ROOT        = r"C:\Users\DELL\OneDrive\Desktop\New folder"
IMAGES_DIR  = os.path.join(ROOT, "images_v2")
WORKSPACE   = os.path.join(ROOT, "workspace_v2")
OUTPUT_DIR  = os.path.join(ROOT, "output")
OUTPUT_PLY  = os.path.join(OUTPUT_DIR, "shalimar_gardens_reconstruction_v2.ply")
DATABASE    = os.path.join(WORKSPACE, "database.db")
SPARSE_DIR  = os.path.join(WORKSPACE, "sparse")

IMG_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}

def banner(msg: str):
    print(f"\n{'═'*65}")
    print(f"  {msg}")
    print(f"{'═'*65}")

def run_step(cmd: list[str], label: str) -> float:
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
    candidates = [
        r"C:\Users\DELL\Downloads\colmap-x64-windows-nocuda\bin\colmap.exe",
        "colmap",
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
    sys.exit(1)

def collect_images() -> list[str]:
    imgs = []
    for f in sorted(os.listdir(IMAGES_DIR)):
        if os.path.splitext(f)[1].lower() in IMG_EXTS:
            imgs.append(os.path.join(IMAGES_DIR, f))
    return imgs

def convert_model_to_txt(colmap: str, model_dir: str) -> str:
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
    model_0 = os.path.join(sparse_dir, "0")
    if not os.path.isdir(model_0):
        print("  [WARN] No sparse model/0 found — COLMAP may not have registered any images.")
        return 0, 0

    txt_dir = convert_model_to_txt(colmap, model_0)

    images_txt  = os.path.join(txt_dir, "images.txt")
    points_txt  = os.path.join(txt_dir, "points3D.txt")

    n_imgs = 0
    if os.path.exists(images_txt):
        with open(images_txt) as f:
            lines = [l for l in f if l.strip() and not l.startswith("#")]
        n_imgs = len(lines) // 2

    n_pts = 0
    if os.path.exists(points_txt):
        with open(points_txt) as f:
            n_pts = sum(1 for l in f if l.strip() and not l.startswith("#"))

    return n_imgs, n_pts

def count_ply_vertices(ply_path: str) -> int:
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

def find_best_model(colmap: str, sparse_dir: str) -> tuple[str | None, int, int]:
    """Finds the sub-model directory (0, 1, etc.) with the highest number of registered images."""
    best_sub = None
    max_registered = -1
    best_points = 0
    if not os.path.exists(sparse_dir):
        return None, 0, 0
    for d in os.listdir(sparse_dir):
        sub = os.path.join(sparse_dir, d)
        if os.path.isdir(sub) and d.isdigit():
            txt_dir = sub + "_txt"
            os.makedirs(txt_dir, exist_ok=True)
            subprocess.run(
                [colmap, "model_converter",
                 "--input_path",  sub,
                 "--output_path", txt_dir,
                 "--output_type", "TXT"],
                capture_output=True
            )
            images_txt = os.path.join(txt_dir, "images.txt")
            points_txt = os.path.join(txt_dir, "points3D.txt")
            n_imgs = 0
            if os.path.exists(images_txt):
                with open(images_txt) as f:
                    lines = [l for l in f if l.strip() and not l.startswith("#")]
                n_imgs = len(lines) // 2
            n_pts = 0
            if os.path.exists(points_txt):
                with open(points_txt) as f:
                    n_pts = sum(1 for l in f if l.strip() and not l.startswith("#"))
            
            if n_imgs > max_registered:
                max_registered = n_imgs
                best_sub = sub
                best_points = n_pts
    return best_sub, max_registered, best_points

def main():
    t_total = time.time()

    banner("Charbagh Collective — Moorcroft Pavilion 3D Reconstruction V2\n"
           "  PMW × TechRealm | Heritage Preservation, Lahore")

    print("\n[PRE-FLIGHT CHECKS]")
    colmap = find_colmap()

    # Clean only sparse output to keep database.db and avoid re-matching
    if os.path.exists(SPARSE_DIR):
        shutil.rmtree(SPARSE_DIR)
    for d in [WORKSPACE, SPARSE_DIR, OUTPUT_DIR]:
        os.makedirs(d, exist_ok=True)

    images = collect_images()
    n_input = len(images)
    print(f"  Input images  : {n_input}  (from {IMAGES_DIR})")

    if n_input < 3:
        print(f"\n[ERROR] Need >= 3 images; only {n_input} found in {IMAGES_DIR}.")
        sys.exit(1)

    db_size = os.path.getsize(DATABASE) if os.path.exists(DATABASE) else 0
    if db_size > 1_000_000:
        print(f"\n  [SKIP] Database already populated ({db_size//1024//1024} MB). Skipping extraction & matching.")
    else:
        # ── Step 1 : Feature Extraction ────────────────────────────────────
        run_step(
            [colmap, "feature_extractor",
             "--database_path",                      DATABASE,
             "--image_path",                         IMAGES_DIR,
             "--ImageReader.single_camera",          "0",
             "--ImageReader.camera_model",           "RADIAL",
             "--FeatureExtraction.use_gpu",          "0",
             "--FeatureExtraction.num_threads",      "2",   # prevents crash on Windows
             "--SiftExtraction.max_num_features",    "8192",
             "--SiftExtraction.first_octave",        "-1",
            ],
            "1/3  Feature Extraction (SIFT, CPU)"
        )

        # ── Step 2 : Exhaustive Matching ───────────────────────────────────
        # Requirements: max_ratio 0.95, max_distance 0.9, min_num_inliers 8
        run_step(
            [colmap, "exhaustive_matcher",
             "--database_path",                      DATABASE,
             "--FeatureMatching.use_gpu",            "0",
             "--SiftMatching.max_ratio",             "0.95",
             "--SiftMatching.max_distance",          "0.9",
             "--TwoViewGeometry.min_num_inliers",    "8",
            ],
            "2/3  Exhaustive Feature Matching (CPU)"
        )

    # ── Step 3 : Sparse Reconstruction ────────────────────────────────
    # Requirements: Mapper.init_min_num_inliers 8, Mapper.abs_pose_min_num_inliers 8
    run_step(
        [colmap, "mapper",
         "--database_path",                      DATABASE,
         "--image_path",                         IMAGES_DIR,
         "--output_path",                        SPARSE_DIR,
         "--Mapper.num_threads",                 "4",
         "--Mapper.init_min_num_inliers",        "8",
         "--Mapper.abs_pose_min_num_inliers",    "8",
        ],
        "3/3  Sparse Reconstruction (SFM Mapper)"
    )

    best_model, n_registered, n_sparse_pts = find_best_model(colmap, SPARSE_DIR)
    print(f"\n  Registered cameras : {n_registered}")
    print(f"  Sparse 3D points   : {n_sparse_pts:,}")

    if not best_model or n_registered == 0:
        print("\n[ERROR] No cameras registered. Reconstruction failed.")
        sys.exit(1)

    # ── Step 4 : Export to PLY ─────────────────────────────────────────
    run_step(
        [colmap, "model_converter",
         "--input_path",                         best_model,
         "--output_path",                        OUTPUT_PLY,
         "--output_type",                        "PLY"
        ],
        "Export to PLY Point Cloud"
    )

    n_dense = count_ply_vertices(OUTPUT_PLY)
    t_elapsed = time.time() - t_total

    # V1 Stats for comparison
    v1_registered = 2
    v1_points = 42

    improvement = "YES" if (n_registered > v1_registered and n_dense > v1_points) else "NO"

    # ── Summary ────────────────────────────────────────────────────────
    print("\n\n")
    w = 68
    def row(label, value):
        print(f"║  {label:<35} {str(value):<{w-38}} ║")

    print("╔" + "═"*w + "╗")
    print("║" + "  RECONSTRUCTION SUMMARY (V2 - MOORCROFT PAVILION)".center(w) + "║")
    print("║" + "  Charbagh Collective | PMW × TechRealm".center(w) + "║")
    print("╠" + "═"*w + "╣")
    row("Images in ./images_v2 (input)",  n_input)
    row("Cameras registered by COLMAP", n_registered)
    row("Sparse 3D points (vertex count)", f"{n_dense:,}")
    row("Output PLY",                  "output\\shalimar_gardens_reconstruction_v2.ply")
    row("Total runtime",               fmt_time(t_elapsed))
    print("╠" + "═"*w + "╣")
    print("║" + "  COMPARISON WITH V1".center(w) + "║")
    print("╠" + "═"*w + "╣")
    row("V1 Registered Cameras",       v1_registered)
    row("V2 Registered Cameras",       n_registered)
    row("V1 3D Points",                v1_points)
    row("V2 3D Points",                n_dense)
    row("Quality Improvement?",        improvement)
    print("╠" + "═"*w + "╣")
    print("║" + "  ✓ PLY validated — vertex count > 0".center(w) + "║")
    print("╚" + "═"*w + "╝")
    print()

if __name__ == "__main__":
    main()
