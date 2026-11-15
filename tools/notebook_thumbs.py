"""Pull one saved chart out of each published notebook as a thumbnail (assets/notebooks/<name>.webp).

The index is which saved image output to use, counted from 0 in notebook order. Rerun after a notebook changes:
    python tools/notebook_thumbs.py
"""
import base64, io, json, pathlib
from PIL import Image

PICK = {
    "broward-investor-guide": 8, "broward-segmentation": 0, "broward-pricing-consistency": 8, "broward-market-analysis": 3,
}
root = pathlib.Path(__file__).resolve().parent.parent
for name, idx in PICK.items():
    nb = json.loads((root / "notebooks" / f"{name}.ipynb").read_text(encoding="utf-8"))
    pngs = [o["data"]["image/png"] for c in nb["cells"] for o in c.get("outputs", []) if "image/png" in o.get("data", {})]
    im = Image.open(io.BytesIO(base64.b64decode(pngs[idx]))).convert("RGB")
    im.thumbnail((1200, 800))
    im.save(root / "assets" / "notebooks" / f"{name}.webp", quality=86)
    print(name, im.size)
