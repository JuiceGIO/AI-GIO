"""从 hf-mirror 下载 bge-small-zh-v1.5 的 ONNX 版本与分词器文件（支持断点续传式重试）。"""
import sys
import time
import urllib.request
from pathlib import Path

REPO = "Xenova/bge-small-zh-v1.5"
BASE = f"https://hf-mirror.com/{REPO}/resolve/main/"
FILES = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "onnx/model_quantized.onnx",
    "onnx/model.onnx",
]


def fetch(name: str, dst_dir: Path, attempts: int = 4) -> bool:
    dst = dst_dir / name.replace("/", "__")
    url = BASE + name
    for attempt in range(1, attempts + 1):
        try:
            t0 = time.time()
            req = urllib.request.Request(url, headers={"User-Agent": "codex"})
            with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f:
                total = 0
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    total += len(chunk)
            dt = time.time() - t0
            print(f"[OK]   {name}: {total / 1048576:.1f}MB 用时 {dt:.0f}s（{total / 1024 / max(dt, 0.1):.0f}KB/s）", flush=True)
            return True
        except Exception as exc:
            print(f"[retry{attempt}] {name}: {type(exc).__name__} {str(exc)[:70]}", flush=True)
            time.sleep(3)
    print(f"[FAIL] {name}", flush=True)
    return False


def main() -> None:
    default_dir = Path(__file__).resolve().parent.parent / "models" / "bge-small-zh-onnx"
    dst_dir = Path(sys.argv[1] if len(sys.argv) > 1 else default_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    for name in FILES:
        if fetch(name, dst_dir):
            ok += 1
    print(f"\n完成：{ok}/{len(FILES)} 个文件 → {dst_dir}")


if __name__ == "__main__":
    main()
