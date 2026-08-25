from pathlib import Path

p = Path("ruffle-src/render/wgpu/src/context3d/current_pipeline.rs")
text = p.read_text()
text = text.replace(
    "            Context3DTriangleFace::FrontAndBack => None\n",
    "            Context3DTriangleFace::FrontAndBack => None,\n",
    1,
)
text = text.replace(
    "        self.culling == Context3DTriangleFace::FrontAndBack\n",
    "        matches!(self.culling, Context3DTriangleFace::FrontAndBack)\n",
    1,
)
p.write_text(text)
print("Fixed V10 FrontAndBack culling compilation")
