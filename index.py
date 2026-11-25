# -*- coding: utf-8 -*-
"""
Rebuild index.npy from catalog.json + the images/ folder.

Run it on your computer, from the folder that contains catalog.json and images/:

    pip install sentence-transformers pillow numpy
    python build_index.py

Then upload the new index.npy to GitHub (replace the old one).
The model and the normalisation are the same ones bot_core.py uses
(clip-ViT-B-32, normalize_embeddings=True), and the rows are in catalog order.
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from sentence_transformers import SentenceTransformer

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, "catalog.json")
IMAGES = os.path.join(HERE, "images")
OUT = os.path.join(HERE, "index.npy")

with open(CATALOG, encoding="utf-8-sig") as f:
    catalog = json.load(f)
print(f"Catalog entries: {len(catalog)}")

old = os.path.join(HERE, "index.npy")
if os.path.exists(old):
    try:
        print(f"Old index.npy rows: {len(np.load(old))}")
    except Exception as exc:
        print(f"Could not read old index.npy: {exc}")

missing = [
    (c.get("code"), c.get("image"))
    for c in catalog
    if not os.path.exists(os.path.join(IMAGES, c.get("image", "")))
]
if missing:
    print("These catalog entries have no image file in images/:")
    for code, image in missing:
        print(f"  {code}: {image}")
    sys.exit("Fix the missing images (or catalog.json) and run again.")

print("Loading clip-ViT-B-32 (first run downloads the model)...")
model = SentenceTransformer("clip-ViT-B-32")

rows = []
for i, c in enumerate(catalog, 1):
    with Image.open(os.path.join(IMAGES, c["image"])) as im:
        rows.append(model.encode(im.convert("RGB"), normalize_embeddings=True))
    print(f"[{i}/{len(catalog)}] {c['code']}")

emb = np.array(rows, dtype=np.float32)
np.save(OUT, emb)
print(f"Saved {OUT} with shape {emb.shape}")
assert len(emb) == len(catalog)
print("OK: index.npy matches catalog.json")
