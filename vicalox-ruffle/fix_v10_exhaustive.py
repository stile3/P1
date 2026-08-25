from pathlib import Path

p = Path("ruffle-src/render/src/atf.rs")
text = p.read_text()
old = '''                            ATFFormat::RGB888
                            | ATFFormat::RGBA8888
                            | ATFFormat::CompressedAlpha => unreachable!(),'''
new = '''                            ATFFormat::RGB888
                            | ATFFormat::RGBA8888
                            | ATFFormat::Compressed
                            | ATFFormat::RawCompressed
                            | ATFFormat::CompressedAlpha => unreachable!(),'''
if old not in text:
    raise SystemExit("ATF fallback unreachable block not found")
p.write_text(text.replace(old, new, 1))
print("Fixed ATF exhaustive fallback match")
