"""
Cleanup Script - Removes obsolete files from the codebase
"""
import os

# Phase 1: Obsolete Models & Datasets
phase1_files = [
    "backend/brain/models/reach_model.pkl",
    "backend/brain/models/reach_scaler.pkl",
    "backend/brain/models/reach_model_performance.png",
    "backend/tools/final_data.csv",
]

# Phase 2: Obsolete Collection/Training Scripts
phase2_files = [
    "backend/collect_data_hybrid.py",
    "backend/collect_data_hybrid_visual.py",
    "backend/train_hybrid.py",
    "backend/main_hybrid.py",
]

# Phase 3: Standalone Runtime
phase3_files = [
    "backend/main_visual_compensation.py",
]

# Phase 4: Obsolete Training Scripts
phase4_files = [
    "backend/brain/train_kinematics.py",
    "backend/brain/train_anfis.py",
    "backend/brain/train_steering.py",
]

# Phase 5: Obsolete Tools
phase5_files = [
    "backend/tools/auto_collect.py",
    "backend/tools/collect_data.py",
    "backend/tools/collect_kinematics.py",
    "backend/tools/training_curve.png",
]

# Phase 6: Obsolete Brain Files
phase6_files = [
    "backend/brain/check_dims.py",
    "backend/brain/grab_controller.py",
    "backend/brain/continuous_grab_controller.py",
    "backend/brain/inspect_models.py",
    "backend/brain/kinematics_engine.py",
]

all_files = phase1_files + phase2_files + phase3_files + phase4_files + phase5_files + phase6_files

print("=" * 70)
print("CODEBASE CLEANUP - Removing Obsolete Files")
print("=" * 70)

deleted_count = 0
skipped_count = 0
failed_count = 0

for filepath in all_files:
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"✅ Deleted: {filepath}")
            deleted_count += 1
        except Exception as e:
            print(f"❌ Failed to delete {filepath}: {e}")
            failed_count += 1
    else:
        print(f"⚠️  Not found (already deleted?): {filepath}")
        skipped_count += 1

print("\n" + "=" * 70)
print(f"CLEANUP COMPLETE")
print(f"  Deleted: {deleted_count} files")
print(f"  Skipped: {skipped_count} files (not found)")
print(f"  Failed:  {failed_count} files")
print("=" * 70)

if failed_count > 0:
    print("\n⚠️  Some files failed to delete. Check permissions or file locks.")
