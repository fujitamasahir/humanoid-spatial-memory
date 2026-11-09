"""Render top-down PNGs of the 36 saved Phase 1.5 fit mazes (no generation)."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPARISON = ROOT / "results/phase2_mujoco/g1_3d_perception_footprint_feedback_full_288"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/phase15_maze_top_views_36"
METHODS = ("R", "BP", "M")
COLORS = {
    "background": "#f5f8fb",
    "header": "#152838",
    "subtitle": "#4c6271",
    "floor": "#e7f0f5",
    "wall": "#203544",
    "grid": "#bdcbd4",
    "start": "#00c9ee",
    "goal": "#f4b928",
    "white": "#ffffff",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def font(size: int, bold: bool = False):
    choices = (
        ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
         "/Library/Fonts/Arial Bold.ttf"] if bold else
        ["/System/Library/Fonts/Supplemental/Arial.ttf",
         "/Library/Fonts/Arial.ttf"]
    )
    for choice in choices:
        if Path(choice).is_file():
            return ImageFont.truetype(choice, size=size)
    return ImageFont.load_default()


def load_candidates(comparison: Path) -> tuple[list[dict], dict]:
    provenance_path = comparison / "provenance.json"
    provenance_bytes = provenance_path.read_bytes()
    provenance = json.loads(provenance_bytes)
    roots = [ROOT / path for path in provenance["source_store_roots"]]
    records = []
    for identity in provenance["world_identities"]:
        parts = identity.split(":fit:", 1)
        if len(parts) != 2:
            raise ValueError(f"Unexpected saved world identity: {identity}")
        mechanism, seed_text = parts[1].split(":", 1)
        if mechanism not in METHODS:
            continue
        record_path = Path("records") / f"{digest(identity.encode())}.json.gz"
        stored_path = next((root / record_path for root in roots
                            if (root / record_path).is_file()), None)
        if stored_path is None:
            raise FileNotFoundError(f"No saved candidate record for {identity}")
        raw = stored_path.read_bytes()
        wrapper = json.loads(gzip.decompress(raw))
        payload = wrapper.get("payload", {})
        if wrapper.get("identity") != identity or payload.get("identity") != identity:
            raise ValueError(f"Stored record identity mismatch: {identity}")
        payload_digest = digest(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                          allow_nan=False).encode())
        if wrapper.get("payload_sha256") != payload_digest:
            raise ValueError(f"Stored record payload hash mismatch: {identity}")
        if payload.get("mechanism") != mechanism or payload.get("partition") != "fit":
            raise ValueError(f"Stored mechanism/partition mismatch: {identity}")
        if payload.get("outcome") != "independent":
            raise ValueError(f"Candidate is not admitted as independent: {identity}")
        geometry = payload.get("geometry", {})
        width, height = int(geometry.get("width", 0)), int(geometry.get("height", 0))
        free = {tuple(map(int, cell)) for cell in geometry.get("free", [])}
        world = payload.get("world", {})
        start, goal = tuple(world.get("start", ())), tuple(world.get("goal", ()))
        if width < 1 or height < 1 or not free or len(start) != 2 or len(goal) != 2:
            raise ValueError(f"Stored maze geometry/start/goal missing: {identity}")
        if start not in free or goal not in free:
            raise ValueError(f"Saved start/goal is not in a free cell: {identity}")
        records.append({
            "identity": identity,
            "mechanism": mechanism,
            "seed": int(seed_text),
            "width": width,
            "height": height,
            "free": free,
            "start": start,
            "goal": goal,
            "source_record": stored_path.relative_to(ROOT).as_posix(),
            "source_record_sha256": digest(raw),
        })
    records.sort(key=lambda row: (METHODS.index(row["mechanism"]), row["seed"]))
    counts = {method: sum(row["mechanism"] == method for row in records) for method in METHODS}
    if len(records) != 36 or counts != {"R": 12, "BP": 12, "M": 12}:
        raise ValueError(f"Expected exactly 12 saved fit mazes per method, got {counts}")
    return records, {"path": provenance_path.relative_to(ROOT).as_posix(),
                     "sha256": digest(provenance_bytes), "counts": counts}


def render_maze(row: dict, *, cell_px: int = 19) -> Image.Image:
    width, height = row["width"], row["height"]
    margin_x, top, footer = 36, 82, 68
    map_w, map_h = width * cell_px, height * cell_px
    image = Image.new("RGB", (map_w + 2 * margin_x, top + map_h + footer), COLORS["background"])
    draw = ImageDraw.Draw(image)
    draw.text((margin_x, 18), f"{row['mechanism']}  /  {row['seed']}",
              fill=COLORS["header"], font=font(28, True))
    draw.text((margin_x, 51), f"Phase 1.5 saved fit maze  •  {width} × {height} cells",
              fill=COLORS["subtitle"], font=font(15))

    x0, y0 = margin_x, top
    for y in range(height):
        for x in range(width):
            # Positive world Y is shown upward, matching the saved world coordinate convention.
            px = x0 + x * cell_px
            py = y0 + (height - 1 - y) * cell_px
            fill = COLORS["floor"] if (x, y) in row["free"] else COLORS["wall"]
            draw.rectangle((px, py, px + cell_px - 1, py + cell_px - 1), fill=fill,
                           outline=COLORS["grid"], width=1)
    draw.rectangle((x0 - 2, y0 - 2, x0 + map_w + 1, y0 + map_h + 1),
                   outline=COLORS["header"], width=3)

    def marker(cell, color, label):
        x, y = cell
        cx = x0 + x * cell_px + cell_px // 2
        cy = y0 + (height - 1 - y) * cell_px + cell_px // 2
        radius = max(7, cell_px // 2 - 1)
        draw.ellipse((cx-radius-3, cy-radius-3, cx+radius+3, cy+radius+3),
                    fill=COLORS["white"])
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=color,
                    outline=COLORS["header"], width=1)
        label_font = font(12, True)
        box = draw.textbbox((0, 0), label, font=label_font)
        draw.text((cx-(box[2]-box[0])/2, cy-(box[3]-box[1])/2-1), label,
                  fill=COLORS["header"], font=label_font)

    marker(row["start"], COLORS["start"], "S")
    marker(row["goal"], COLORS["goal"], "G")
    legend_y = y0 + map_h + 20
    for cx, color, label, coord in (
        (margin_x, COLORS["start"], "START", row["start"]),
        (margin_x + 220, COLORS["goal"], "GOAL", row["goal"]),
    ):
        draw.ellipse((cx, legend_y, cx+18, legend_y+18), fill=color,
                     outline=COLORS["header"], width=1)
        draw.text((cx+26, legend_y), f"{label}  ({coord[0]}, {coord[1]})",
                  fill=COLORS["header"], font=font(15, True))
    return image


def contact_sheet(rows: list[dict], images: list[Image.Image], *, cols: int,
                  cell_size=(286, 340), title="Saved maze top views") -> Image.Image:
    rows_n = (len(images) + cols - 1) // cols
    tile_w, tile_h = cell_size
    pad, title_h = 22, 70
    sheet = Image.new("RGB", (pad + cols * tile_w, title_h + rows_n * (tile_h + 14) + pad),
                      COLORS["background"])
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 18), title, fill=COLORS["header"], font=font(32, True))
    for i, (row, image) in enumerate(zip(rows, images)):
        thumb = image.copy()
        thumb.thumbnail((tile_w - 18, tile_h - 48), Image.Resampling.LANCZOS)
        x = pad + (i % cols) * tile_w
        y = title_h + (i // cols) * (tile_h + 14)
        draw.rounded_rectangle((x, y, x+tile_w-8, y+tile_h), radius=10,
                               fill=COLORS["white"], outline="#d4dee5", width=2)
        draw.text((x+10, y+7), f"{row['mechanism']}  {row['seed']}",
                  fill=COLORS["header"], font=font(16, True))
        sheet.paste(thumb, (x + (tile_w-thumb.width)//2,
                            y + 32 + (tile_h-48-thumb.height)//2))
    return sheet


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison-dir", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    comparison = args.comparison_dir.resolve()
    output = args.output_dir.resolve()
    if output.exists():
        parser.error(f"Refusing to overwrite existing output directory: {output}")
    rows, source_info = load_candidates(comparison)
    output.mkdir(parents=True)
    images_by_method = {}
    manifest_rows = []
    for row in rows:
        image = render_maze(row)
        method_dir = output / row["mechanism"]
        method_dir.mkdir(exist_ok=True)
        path = method_dir / f"{row['mechanism']}_{row['seed']}.png"
        image.save(path, optimize=True)
        row_image = {key: value for key, value in row.items() if key != "free"}
        row_image["image"] = path.relative_to(output).as_posix()
        row_image["free_cell_count"] = len(row["free"])
        row_image["image_sha256"] = digest(path.read_bytes())
        manifest_rows.append(row_image)
        images_by_method.setdefault(row["mechanism"], []).append((row, image))

    for method in METHODS:
        group = images_by_method[method]
        contact_sheet([r for r, _ in group], [im for _, im in group], cols=4,
                      title=f"{method} saved fit mazes · 12 worlds").save(
                          output / f"overview_{method}.png", optimize=True)
    all_images = [(row, image) for method in METHODS for row, image in images_by_method[method]]
    contact_sheet([r for r, _ in all_images], [im for _, im in all_images], cols=6,
                  cell_size=(220, 258), title="Phase 1.5 fit mazes · 36 saved worlds").save(
                      output / "overview_all_36.png", optimize=True)

    metadata = {
        "title": "Phase 1.5 saved fit maze top views",
        "source_comparison_dir": comparison.relative_to(ROOT).as_posix(),
        "source_provenance": source_info,
        "selection": "The 36 world identities listed in the existing completed Phase 2 288-episode provenance: 12 each for R, BP, M. No environment was regenerated.",
        "rendering": {"projection": "top-down orthographic grid", "cell_size_px": 19,
                      "free_cell_color": COLORS["floor"], "wall_color": COLORS["wall"],
                      "start_marker": COLORS["start"], "goal_marker": COLORS["goal"],
                      "coordinate_convention": "x increases right; positive world y increases upward"},
        "count_by_method": source_info["counts"],
        "mazes": manifest_rows,
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    (output / "README.md").write_text(
        "# Saved Phase 1.5 maze top views\n\n"
        "This package contains all 36 existing fit mazes used by the completed Phase 2 comparison: "
        "12 each from R, BP, and M. The maze geometry, start, and goal were read from the corresponding "
        "saved candidate records. No maze generation or experiment execution occurred.\n\n"
        "Start is marked cyan (S); goal is gold (G). Coordinates are saved grid `(x, y)` values; "
        "positive y is shown upward. See `overview_all_36.png` for the full contact sheet, "
        "`overview_R.png`, `overview_BP.png`, and `overview_M.png` for method sheets, and `metadata.json` "
        "for identities and source hashes. Individual diagrams are in the R, BP, and M folders.\n")
    cards = []
    for row in manifest_rows:
        cards.append(
            f'<a class="card" href="{html.escape(row["image"])}">'
            f'<img src="{html.escape(row["image"])}" loading="lazy">'
            f'<b>{html.escape(row["mechanism"])} · {row["seed"]}</b></a>')
    (output / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>36 saved mazes</title>"
        "<style>body{font:16px system-ui;background:#f5f8fb;color:#152838;margin:2rem}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem}"
        ".card{background:white;padding:.7rem;border-radius:.8rem;color:inherit;text-decoration:none}"
        ".card img{width:100%;height:auto;display:block}.card b{display:block;padding:.5rem}</style>"
        "<h1>Phase 1.5 saved maze top views</h1><p>36 existing mazes · 12 each R, BP, M · "
        "cyan start / gold goal</p><p><a href='overview_all_36.png'>All 36 overview</a> · "
        "<a href='overview_R.png'>R</a> · <a href='overview_BP.png'>BP</a> · "
        "<a href='overview_M.png'>M</a></p><div class='grid'>" + "\n".join(cards) + "</div>\n")
    print(json.dumps({"status": "PASS_RENDERED_SAVED_MAZES", "output": str(output),
                      "counts": source_info["counts"], "individual_pngs": len(manifest_rows),
                      "overviews": 4}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
