#!/usr/bin/env python3
"""
Corpus Directory Importer
Recursively imports an entire folder of layout files (PDF, IDML, PNG, JPG, WEBP, SVG, TIFF)
into a specific newspaper project's corpus and automatically triggers TitleDNA learning.
"""

import argparse
import sys
import os
import uuid
import shutil
from pathlib import Path

# Add project root to python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.models.database import db
from backend.app.models.schemas import CorpusPage, Project
from backend.app.api.corpus import extract_features_from_file, learn_dna_from_corpus
from backend.app.config import settings

SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".idml": "idml",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".tiff": "image",
    ".tif": "image",
    ".svg": "image"
}

def import_directory(project_id: str, directory_path: Path, recursive: bool = True):
    if not directory_path.exists() or not directory_path.is_dir():
        print(f"❌ Error: Directory '{directory_path}' does not exist or is not a directory.")
        sys.exit(1)

    proj = db.get_project(project_id)
    if not proj:
        # List available projects
        projects = db.list_projects()
        print(f"❌ Error: Project with ID '{project_id}' not found.")
        if projects:
            print("\nAvailable projects:")
            for p in projects:
                # Format is stored in the project's TitleDNA, not on the
                # Project record.  Avoid dereferencing the removed legacy
                # ``Project.format_preset`` field while listing candidates.
                dna = db.get_title_dna(p.id)
                format_name = dna.format.trim_w_mm if dna else "unknown"
                format_label = f"{format_name:g}mm" if isinstance(format_name, (int, float)) else str(format_name)
                print(f" • ID: {p.id}  |  Name: {p.name}  |  Format width: {format_label}")
        else:
            print("No projects exist yet. Create a project first via the UI or API.")
        sys.exit(1)

    print("=" * 65)
    print(f" 📂 NEWSPAPER CORPUS BATCH IMPORTER")
    print("=" * 65)
    print(f" • Target Project: {proj.name} (ID: {proj.id})")
    print(f" • Source Folder:  {directory_path}")
    print(f" • Recursive:      {recursive}")
    print("-" * 65)

    files_found = []
    pattern = "**/*" if recursive else "*"
    for p in directory_path.glob(pattern):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
            files_found.append(p)

    if not files_found:
        print(f"⚠️  No supported layout files found in '{directory_path}'.")
        print(f"   Supported extensions: {', '.join(SUPPORTED_EXTENSIONS.keys())}")
        sys.exit(0)

    print(f"🚀 Found {len(files_found)} layout file(s) to import...\n")

    imported_count = 0
    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    for idx, file_path in enumerate(files_found, 1):
        ext = file_path.suffix.lower()
        file_type = SUPPORTED_EXTENSIONS[ext]
        file_id = str(uuid.uuid4())
        saved_filename = f"corpus_{project_id}_{file_id}{ext}"
        saved_path = settings.UPLOADS_DIR / saved_filename

        # Copy file to project uploads storage
        shutil.copy2(file_path, saved_path)

        # Extract features
        features = extract_features_from_file(saved_path, file_type)

        page_title = file_path.stem.replace("-", " ").replace("_", " ").title()

        corpus_page = CorpusPage(
            id=file_id,
            project_id=project_id,
            title=page_title,
            file_path=str(saved_path),
            file_type=file_type,
            extracted_features=features
        )
        db.add_corpus_page(corpus_page)
        imported_count += 1
        print(f" [{idx}/{len(files_found)}] ✅ Imported: {file_path.name} ({file_type.upper()})")

    print("-" * 65)
    print(f"⚡ Calibrating and learning TitleDNA from {imported_count} corpus page(s)...")
    updated_dna = learn_dna_from_corpus(project_id)

    print("\n" + "=" * 65)
    print(" 🎉 BATCH IMPORT & LEARNING COMPLETED SUCCESSFULLY!")
    print("=" * 65)
    print(f" • Total Pages in Corpus:    {len(db.list_corpus_pages(project_id))}")
    print(f" • Updated TitleDNA Version: v{updated_dna.version}")
    print(f" • Calibrated Energy Budget: {updated_dna.page_energy_budget}")
    print(f" • Grid Columns:             {updated_dna.grid.columns}")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch import an entire directory of layout files into a newspaper project.")
    parser.add_argument("--project-id", type=str, required=True, help="Project ID (e.g. 'proj-chronicle')")
    parser.add_argument("--dir", type=str, required=True, help="Path to folder containing layout files (PDF, IDML, images)")
    parser.add_argument("--no-recursive", action="store_true", help="Do not scan subdirectories recursively")

    args = parser.parse_args()
    import_directory(
        project_id=args.project_id,
        directory_path=Path(args.dir).resolve(),
        recursive=not args.no_recursive
    )
