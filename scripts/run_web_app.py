"""Launch script for GSM Memory Conversational QA Web Interface."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure src in sys.path
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import uvicorn
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "127.0.0.1")

    print("=" * 72)
    print("  🚕 KHỞI CHẠY GIAO DIỆN HỎI ĐÁP QUY CHẾ & VẬN HÀNH GSM (TAXI XANH SM)")
    print("=" * 72)
    print(f"  🌐 URL Giao diện Web:    http://{host}:{port}")
    print(f"  📚 Tài liệu API Docs:    http://{host}:{port}/docs")
    print(f"  ⚡ Model LLM:           {os.getenv('OPENROUTER_MODEL', 'nvidia/nemotron-3.5-lightning:free')}")
    print(f"  🔍 Kho chính sách:       44 chunks (debug_core@1)")
    print("=" * 72)
    print("  Nhấn CTRL+C để dừng máy chủ.\n")

    uvicorn.run(
        "gsm_memory.web.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
