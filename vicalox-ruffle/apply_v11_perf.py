from pathlib import Path

ROOT = Path("ruffle-src")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    if old not in text:
        raise SystemExit(f"{label}: anchor not found in {path}")
    path.write_text(text.replace(old, new, 1))


# ---------------------------------------------------------------------------
# Vicalox V11 Turbo: malformed/variant ATF data must never panic the whole VM.
# V10 used the upstream expect(), which destroys the Ruffle instance on one
# texture that our old MU client stores in a slightly different ATF variant.
# Skip that texture and keep the game alive instead.
# ---------------------------------------------------------------------------
atf_upload = ROOT / "core/src/avm2/globals/flash/display3D/textures/atf_jpegxr.rs"
replace_once(
    atf_upload,
    '    let atf_texture = ATFTexture::from_bytes(raw_atf).expect("Failed to parse ATF texture");',
    '''    let atf_texture = match ATFTexture::from_bytes(raw_atf) {
        Ok(texture) => texture,
        Err(error) => {
            tracing::warn!("Vicalox: skipping malformed/unsupported ATF texture: {error}");
            return Ok(());
        }
    };''',
    "ATF parse panic guard",
)


# ---------------------------------------------------------------------------
# Vicalox V11 Turbo: disable Stage3D MSAA in the browser build.
# Legacy Flare3D requests anti-aliasing, but on wgpu-webgl this multiplies
# render-target bandwidth and resolve work. The original 1280x720 art does not
# need expensive MSAA when the browser is already scaling the final canvas.
# Native/desktop Ruffle behavior remains unchanged.
# ---------------------------------------------------------------------------
wgpu_ctx = ROOT / "render/wgpu/src/context3d/mod.rs"
text = wgpu_ctx.read_text()
old = "                let mut sample_count = anti_alias;"
new = '''                let mut sample_count = if cfg!(target_family = "wasm") {
                    1
                } else {
                    anti_alias
                };'''
count = text.count(old)
if count < 2:
    raise SystemExit(f"Stage3D MSAA anchors: expected >=2, got {count}")
# ConfigureBackBuffer and SetRenderToTexture.
text = text.replace(old, new, 2)
wgpu_ctx.write_text(text)

print("Vicalox V11 Turbo performance/stability patches applied")
