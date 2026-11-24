"""Drop-In CLI for Incremental Personal Aesthetic Atlas Ingestion.

Usage:
  python -m pipeline.ingest_dropin path/to/image_or_folder [--source "新灵感导入"]

Automatically runs 64-bit dHash dedup against all existing 500+ assets, classifies & critiques
via `gemini-4-hydrogen`, embeds via `gemini-embedding-2`, projects onto the 2D Semantic Map,
and appends cleanly to `aethervault_personal_500.json`, `aethervault_rag_500.jsonl`, and
`embeddings_500.npz`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .atlas_rag_engine import ingest_images

VALID_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Incrementally ingest new design images into AetherVault Atlas.")
    parser.add_argument("target", help="Path to a single image file or a directory of images")
    parser.add_argument("--source", default="Drop-In CLI 导入", help="Source/board label for newly ingested images")
    args = parser.parse_args()

    target = Path(args.target)
    if not target.exists():
        raise FileNotFoundError(f"Target path does not exist: {target}")

    files = [target] if target.is_file() else sorted(p for p in target.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXTS)
    if not files:
        print("No valid image files (.jpg/.jpeg/.png/.webp) found.")
        return

    payload = [(p.name, p.read_bytes()) for p in files]
    print(f"Ingesting {len(payload)} image(s) from {target}...")
    result = ingest_images(payload, source_label=args.source)
    for item in result["items"]:
        if item["status"] == "added":
            print(
                f"  [ADDED] {item['filename']} -> {item['asset_id']} | "
                f"{item['archetype_label']} · {item['aesthetic_style_zh']} ({item['native_style_primary']}) | {item['title']}"
            )
        else:
            print(f"  [{item['status'].upper()}] {item['filename']} — {item.get('reason', '')}")
    print(
        f"Summary: added={result['added_count']}, skipped={result['skipped_count']}, "
        f"total_assets={result['total_assets']} ({result['latency_ms']:.0f} ms)"
    )


if __name__ == "__main__":
    main()
