import os
import shutil
from pathlib import Path

# -----------------------------
# Helper
# -----------------------------
def safe_move(src, dst):
    """Move file only if it exists."""
    if os.path.exists(src):
        print(f"Moving {src} → {dst}")
        shutil.move(src, dst)

# -----------------------------
# 1. Define directory structure
# -----------------------------
root = Path(".")

folders_to_create = [
    "src",
    "src/extraction",
    "src/preprocessing",
    "src/dataset",
    "src/models",
    "src/training",
    "src/analysis",
    "src/pipeline",
    "src/config",
    "tests",
]

for folder in folders_to_create:
    Path(folder).mkdir(parents=True, exist_ok=True)
    init_file = Path(folder) / "__init__.py"
    if not init_file.exists():
        init_file.write_text("")

print("📁 Folder structure created.")

# -----------------------------
# 2. Move files into new folders
# -----------------------------

# Extraction-related files
safe_move("extract_events_CORRECTED.py", "src/extraction/extract_events_CORRECTED.py")
safe_move("extract_all_records.py", "src/extraction/extract_all_records.py")
safe_move("diagnose_file.py", "src/extraction/diagnose_file.py")

# Preprocessing files
safe_move("build_graph_dataset.py", "src/preprocessing/build_graph_dataset.py")
safe_move("find_interesting_patterns.py", "src/preprocessing/find_interesting_patterns.py")
safe_move("simple_data_exploration.py", "src/preprocessing/simple_data_exploration.py")

# Dataset files
safe_move("sentinel_pyg_dataset.py", "src/dataset/sentinel_pyg_dataset.py")

# Test files
safe_move("test_dataset_loader.py", "tests/test_dataset_loader.py")

# Analysis files
safe_move("Reference.txt", "src/analysis/Reference.txt")
safe_move("STATUS.md", "src/analysis/STATUS.md")

# Reports (Optional)
if not os.path.exists("reports"):
    os.mkdir("reports")
safe_move("Report_!.docx", "reports/Report_!.docx")

print("📦 Files moved successfully!")

# -----------------------------
# 3. Summary
# -----------------------------
print("\n🎉 Reorganization Complete!")
print("Your SENTINEL project now has a clean research structure.")
