# Shalimar Gardens - 3D Reconstruction

COLMAP-based Structure-from-Motion pipeline for Shalimar Gardens, Lahore, built as part of the PMW × TechRealm heritage preservation internship (Team Charbagh Collective).

## Results

**V1:** 43 general Wikimedia Commons images → 2/43 registered → 42 sparse 3D points
**V2:** 15 tightly-overlapping images of the Moorcroft Pavilion → 15/15 registered (100%) → 842 sparse 3D points (20x improvement)

Dense reconstruction (patch-match stereo) requires a CUDA GPU, unavailable on the local machine used — sparse point clouds are the final deliverable for this run.

## Files
- `shalimar_gardens_reconstruction.ply` / `_v2.ply` — sparse point cloud outputs
- `run_reconstruction.py` / `_v2.py` — pipeline scripts
- `download_images.py` / `_v2.py` — image curation scripts
- `point_cloud_screenshot.png` / `_v2_screenshot.png` — visualizations
