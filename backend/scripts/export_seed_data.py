"""export_seed_data.py — `import_business_tools.py export` への互換エントリポイント。

旧ITヘルプデスクのExcelは廃止し、Seedは業務ツール4ファイルから生成する。
"""
from __future__ import annotations

import sys

from import_business_tools import main

if __name__ == "__main__":
    raise SystemExit(main(["export", *sys.argv[1:]]))
