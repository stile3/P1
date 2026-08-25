from pathlib import Path

ROOT = Path("ruffle-src")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    if old not in text:
        raise SystemExit(f"{label}: anchor not found in {path}")
    path.write_text(text.replace(old, new, 1))


# ---------------------------------------------------------------------------
# AGAL2 limits used by Flare3D shaders (vc0..vc249 / fc0..fc63)
# ---------------------------------------------------------------------------
replace_once(
    ROOT / "render/naga-agal/src/builder.rs",
    "const VERTEX_PROGRAM_CONSTANTS: u64 = 128;\nconst FRAGMENT_PROGRAM_CONSTANTS: u64 = 28;",
    "// Vicalox: full AGAL2 register space.\nconst VERTEX_PROGRAM_CONSTANTS: u64 = 250;\nconst FRAGMENT_PROGRAM_CONSTANTS: u64 = 64;",
    "AGAL translator constants",
)
replace_once(
    ROOT / "render/wgpu/src/context3d/current_pipeline.rs",
    "const AGAL_NUM_VERTEX_CONSTANTS: u64 = 128;\nconst AGAL_NUM_FRAGMENT_CONSTANTS: u64 = 28;",
    "// Vicalox: full AGAL2 constant buffers.\nconst AGAL_NUM_VERTEX_CONSTANTS: u64 = 250;\nconst AGAL_NUM_FRAGMENT_CONSTANTS: u64 = 64;",
    "AGAL WGPU buffers",
)


# ---------------------------------------------------------------------------
# Flash API compatibility required by Flare3D/UI
# ---------------------------------------------------------------------------
matrix = ROOT / "core/src/avm2/globals/flash/geom/Matrix3D.as"
text = matrix.read_text()
if "function interpolateTo(" not in text:
    anchor = "        public function append(lhs:Matrix3D):void {"
    method = '''        // Vicalox/Flare3D compatibility.\n        public function interpolateTo(toMat:Matrix3D, percent:Number):void {\n            if (toMat == null) {\n                throw new TypeError("Error #2007: Parameter toMat must be non-null.", 2007);\n            }\n            for (var i:int = 0; i < 16; i++) {\n                this._rawData[i] = this._rawData[i] + (toMat._rawData[i] - this._rawData[i]) * percent;\n            }\n        }\n\n        public static function interpolate(thisMat:Matrix3D, toMat:Matrix3D, percent:Number):Matrix3D {\n            if (thisMat == null || toMat == null) {\n                throw new TypeError("Error #2007: Parameter must be non-null.", 2007);\n            }\n            var out:Matrix3D = new Matrix3D(thisMat._rawData);\n            out.interpolateTo(toMat, percent);\n            return out;\n        }\n\n'''
    if anchor not in text:
        raise SystemExit("Matrix3D anchor not found")
    matrix.write_text(text.replace(anchor, method + anchor, 1))

textblock = ROOT / "core/src/avm2/globals/flash/text/engine/TextBlock.as"
text = textblock.read_text()
if "function releaseLineCreationData(" not in text:
    anchor = "        public function releaseLines(start:TextLine, end:TextLine):void {"
    method = '''        public function releaseLineCreationData():void {\n            // Ruffle does not retain Flash FTE line-creation cache data.\n        }\n\n'''
    if anchor not in text:
        raise SystemExit("TextBlock anchor not found")
    textblock.write_text(text.replace(anchor, method + anchor, 1))


# ---------------------------------------------------------------------------
# ATF format 2/3 support: recover DXT1 and decode to RGBA8
# ---------------------------------------------------------------------------
atf = ROOT / "render/src/atf.rs"
replace_once(
    atf,
    '''    CompressedAlpha {\n        jpegxr_alpha: Vec<u8>,\n        dxt1_alpha_compressed: Vec<u8>,\n        jpegxr_bgr: Vec<u8>,\n        dxt5_rgb_compressed: Vec<u8>,\n    },''',
    '''    // ATF format 2: DXT1 selector bits + JPEG-XR RGB565 endpoints.\n    Compressed {\n        dxt1_indices_compressed: Vec<u8>,\n        jpegxr_colors: Vec<u8>,\n    },\n    // ATF format 3: raw platform-compressed payloads.\n    CompressedRaw {\n        dxt1: Vec<u8>,\n    },\n    CompressedAlpha {\n        jpegxr_alpha: Vec<u8>,\n        dxt1_alpha_compressed: Vec<u8>,\n        jpegxr_bgr: Vec<u8>,\n        dxt5_rgb_compressed: Vec<u8>,\n    },''',
    "ATF enum",
)

replace_once(
    atf,
    "                    ATFFormat::CompressedAlpha => {",
    '''                    ATFFormat::Compressed => {\n                        let bits_len = read_len(bytes)? as usize;\n                        let mut dxt1_indices_compressed = vec![0; bits_len];\n                        bytes.read_exact(&mut dxt1_indices_compressed)?;\n\n                        let colors_len = read_len(bytes)? as usize;\n                        let mut jpegxr_colors = vec![0; colors_len];\n                        bytes.read_exact(&mut jpegxr_colors)?;\n\n                        // ATF v0: DXT1 + PVRTC + ETC1 = 8 records.\n                        // Extended versions add ETC2 = 11 records.\n                        let remaining_records = if version == 0 { 6 } else { 9 };\n                        for _ in 0..remaining_records {\n                            let len = read_len(bytes)? as usize;\n                            *bytes = &bytes[len..];\n                        }\n                        face_mip_data[face].push(ATFTextureData::Compressed {\n                            dxt1_indices_compressed,\n                            jpegxr_colors,\n                        });\n                    }\n                    ATFFormat::RawCompressed => {\n                        let dxt1_len = read_len(bytes)? as usize;\n                        let mut dxt1 = vec![0; dxt1_len];\n                        bytes.read_exact(&mut dxt1)?;\n                        for _ in 0..3 {\n                            let len = read_len(bytes)? as usize;\n                            *bytes = &bytes[len..];\n                        }\n                        face_mip_data[face].push(ATFTextureData::CompressedRaw { dxt1 });\n                    }\n                    ATFFormat::CompressedAlpha => {''',
    "ATF compressed match",
)

replace_once(
    atf,
    '''                            ATFFormat::RawCompressed | ATFFormat::RawCompressedAlpha => 4,\n                            ATFFormat::Compressed => 11,''',
    '''                            ATFFormat::RawCompressedAlpha => 4,''',
    "ATF fallback records",
)


# ---------------------------------------------------------------------------
# Decode reconstructed DXT1 to RGBA. Ruffle maps COMPRESSED RGB textures to
# Rgba8Unorm, so CPU decompression is portable even when browser S3TC varies.
# ---------------------------------------------------------------------------
dec = ROOT / "core/src/avm2/globals/flash/display3D/textures/atf_jpegxr.rs"
text = dec.read_text()
anchor = "        ATFTextureData::CompressedAlpha {"
arm = r'''        ATFTextureData::Compressed {
            dxt1_indices_compressed,
            jpegxr_colors,
        } => {
            let block_x = std::cmp::max(1, atf_texture.width.div_ceil(4));
            let block_y = std::cmp::max(1, atf_texture.height.div_ceil(4));
            let block_count = (block_x * block_y) as usize;

            let mut packed = dxt1_indices_compressed.clone();
            packed.splice(5..5, u64::MAX.to_le_bytes());
            let mut selectors = Vec::with_capacity(block_count * 4);
            lzma_rs::lzma_decompress(&mut packed.as_slice(), &mut selectors)
                .expect("Failed to decompress ATF DXT1 selectors");
            if selectors.len() < block_count * 4 {
                return Err("ATF DXT1 selector stream is too small".into());
            }

            let color_height = std::cmp::max(2, block_y * 2);
            let colors = jpegxr_to_raw_pixels(
                block_x,
                color_height,
                &mut Cursor::new(jpegxr_colors),
            );
            let half_bytes = block_count * 2;
            if colors.len() < half_bytes * 2 {
                return Err("ATF DXT1 color stream is too small".into());
            }

            let mut dxt1 = Vec::with_capacity(block_count * 8);
            for i in 0..block_count {
                dxt1.extend_from_slice(&colors[i * 2..i * 2 + 2]);
                let c1 = half_bytes + i * 2;
                dxt1.extend_from_slice(&colors[c1..c1 + 2]);
                dxt1.extend_from_slice(&selectors[i * 4..i * 4 + 4]);
            }
            decode_dxt1_rgba(&dxt1, atf_texture.width, atf_texture.height)?
        }
        ATFTextureData::CompressedRaw { dxt1 } => {
            decode_dxt1_rgba(dxt1, atf_texture.width, atf_texture.height)?
        }
'''
if anchor not in text:
    raise SystemExit("ATF decoder arm anchor not found")
text = text.replace(anchor, arm + anchor, 1)

helper_anchor = "fn jpegxr_to_raw_pixels<R: Read + Seek>"
helper = r'''fn decode_dxt1_rgba(
    dxt1: &[u8],
    width: u32,
    height: u32,
) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let blocks_x = std::cmp::max(1, width.div_ceil(4));
    let blocks_y = std::cmp::max(1, height.div_ceil(4));
    let needed = blocks_x as usize * blocks_y as usize * 8;
    if dxt1.len() < needed {
        return Err(format!("DXT1 data too short: {} < {}", dxt1.len(), needed).into());
    }

    fn rgb565(c: u16) -> [u8; 3] {
        let r5 = ((c >> 11) & 0x1f) as u8;
        let g6 = ((c >> 5) & 0x3f) as u8;
        let b5 = (c & 0x1f) as u8;
        [
            (r5 << 3) | (r5 >> 2),
            (g6 << 2) | (g6 >> 4),
            (b5 << 3) | (b5 >> 2),
        ]
    }

    let mut out = vec![0u8; width as usize * height as usize * 4];
    for by in 0..blocks_y {
        for bx in 0..blocks_x {
            let bi = ((by * blocks_x + bx) * 8) as usize;
            let c0 = u16::from_le_bytes([dxt1[bi], dxt1[bi + 1]]);
            let c1 = u16::from_le_bytes([dxt1[bi + 2], dxt1[bi + 3]]);
            let p0 = rgb565(c0);
            let p1 = rgb565(c1);
            let mut palette = [[0u8; 4]; 4];
            palette[0] = [p0[0], p0[1], p0[2], 255];
            palette[1] = [p1[0], p1[1], p1[2], 255];
            if c0 > c1 {
                palette[2] = [
                    ((2 * p0[0] as u16 + p1[0] as u16) / 3) as u8,
                    ((2 * p0[1] as u16 + p1[1] as u16) / 3) as u8,
                    ((2 * p0[2] as u16 + p1[2] as u16) / 3) as u8,
                    255,
                ];
                palette[3] = [
                    ((p0[0] as u16 + 2 * p1[0] as u16) / 3) as u8,
                    ((p0[1] as u16 + 2 * p1[1] as u16) / 3) as u8,
                    ((p0[2] as u16 + 2 * p1[2] as u16) / 3) as u8,
                    255,
                ];
            } else {
                palette[2] = [
                    ((p0[0] as u16 + p1[0] as u16) / 2) as u8,
                    ((p0[1] as u16 + p1[1] as u16) / 2) as u8,
                    ((p0[2] as u16 + p1[2] as u16) / 2) as u8,
                    255,
                ];
                palette[3] = [0, 0, 0, 0];
            }

            let lookup = u32::from_le_bytes([
                dxt1[bi + 4], dxt1[bi + 5], dxt1[bi + 6], dxt1[bi + 7],
            ]);
            for py in 0..4u32 {
                for px in 0..4u32 {
                    let x = bx * 4 + px;
                    let y = by * 4 + py;
                    if x >= width || y >= height {
                        continue;
                    }
                    let pi = ((lookup >> (2 * (py * 4 + px))) & 3) as usize;
                    let dst = ((y * width + x) * 4) as usize;
                    out[dst..dst + 4].copy_from_slice(&palette[pi]);
                }
            }
        }
    }
    Ok(out)
}

'''
if helper_anchor not in text:
    raise SystemExit("ATF helper anchor not found")
dec.write_text(text.replace(helper_anchor, helper + helper_anchor, 1))


# Allow normal compressed textures through the ATF upload path.
tex = ROOT / "core/src/avm2/globals/flash/display3D/textures/texture.rs"
replace_once(
    tex,
    "        Context3DTextureFormat::Bgra | Context3DTextureFormat::CompressedAlpha",
    "        Context3DTextureFormat::Bgra\n            | Context3DTextureFormat::Compressed\n            | Context3DTextureFormat::CompressedAlpha",
    "compressed texture gate",
)

# Remove obsolete createTexture(COMPRESSED) stub log.
obj = ROOT / "core/src/avm2/object/context3d_object.rs"
text = obj.read_text()
block = '''        Context3DTextureFormat::Compressed => {\n            avm2_stub_method!(\n                activation,\n                "flash.display3D.Context3D",\n                "createTexture",\n                "with Compressed"\n            );\n        }\n'''
if block in text:
    obj.write_text(text.replace(block, "", 1))


# ---------------------------------------------------------------------------
# FRONT_AND_BACK: Adobe culls every triangle. WGPU only exposes one-face cull,
# so render an empty indexed range for that state.
# ---------------------------------------------------------------------------
pipeline = ROOT / "render/wgpu/src/context3d/current_pipeline.rs"
replace_once(
    pipeline,
    '''            Context3DTriangleFace::FrontAndBack => {\n                tracing::error!("FrontAndBack culling not supported!");\n                None\n            }''',
    '''            // Emulated by drawTriangles using an empty index range.\n            Context3DTriangleFace::FrontAndBack => None''',
    "FrontAndBack pipeline",
)
text = pipeline.read_text()
anchor = "    pub fn new(descriptors: &Descriptors) -> Self {"
method = '''    pub fn culls_all_triangles(&self) -> bool {\n        self.culling == Context3DTriangleFace::FrontAndBack\n    }\n\n'''
if "pub fn culls_all_triangles" not in text:
    if anchor not in text:
        raise SystemExit("CurrentPipeline method anchor not found")
    pipeline.write_text(text.replace(anchor, method + anchor, 1))

ctx = ROOT / "render/wgpu/src/context3d/mod.rs"
replace_once(
    ctx,
    '''                let indices =\n                    (first_index as u32)..((first_index as u32) + (num_triangles as u32 * 3));''',
    '''                let indices = if self.current_pipeline.culls_all_triangles() {\n                    0..0\n                } else {\n                    (first_index as u32)..((first_index as u32) + (num_triangles as u32 * 3))\n                };''',
    "DrawTriangles culling",
)

print("Vicalox V10 patches applied successfully")
