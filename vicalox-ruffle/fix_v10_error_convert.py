from pathlib import Path

p = Path("ruffle-src/core/src/avm2/globals/flash/display3D/textures/atf_jpegxr.rs")
text = p.read_text()
old1 = "            decode_dxt1_rgba(&dxt1, atf_texture.width, atf_texture.height)?\n"
new1 = "            decode_dxt1_rgba(&dxt1, atf_texture.width, atf_texture.height)\n                .map_err(|e| e.to_string())?\n"
old2 = "            decode_dxt1_rgba(dxt1, atf_texture.width, atf_texture.height)?\n"
new2 = "            decode_dxt1_rgba(dxt1, atf_texture.width, atf_texture.height)\n                .map_err(|e| e.to_string())?\n"
if old1 not in text or old2 not in text:
    raise SystemExit("DXT1 error conversion anchors not found")
text = text.replace(old1, new1, 1).replace(old2, new2, 1)
p.write_text(text)
print("Fixed V10 DXT1 AVM2 error conversion")
