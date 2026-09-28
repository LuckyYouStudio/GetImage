#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 index.html 内联进 Worker 模板，生成可直接粘贴到 Cloudflare 控制台的 dist/worker.js。

用法（在仓库根目录）：
    python deploy/build_worker.py

每次改了 index.html 都要重新跑一次，然后把新的 dist/worker.js 粘贴回 Cloudflare。
"""

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_HTML = os.path.join(ROOT, "index.html")
SRC_TPL = os.path.join(ROOT, "deploy", "worker.src.js")
OUT = os.path.join(ROOT, "dist", "worker.js")


def js_string(s: str) -> str:
    # JSON 字符串字面量在 JS 里合法，只有 U+2028 / U+2029 例外，单独转义掉
    return json.dumps(s, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def main() -> int:
    html = io.open(SRC_HTML, encoding="utf-8").read()
    tpl = io.open(SRC_TPL, encoding="utf-8").read()
    # 只替换赋值语句本身，模板注释里提到的 __HTML__ 不动
    marker = "const HTML = __HTML__;"
    if tpl.count(marker) != 1:
        print("模板里应恰好有一句 `%s`" % marker, file=sys.stderr)
        return 1
    out = tpl.replace(marker, "const HTML = %s;" % js_string(html))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(out)
    print("已生成 %s（%.1f KB，其中页面 %.1f KB）" % (
        os.path.relpath(OUT, ROOT), len(out.encode("utf-8")) / 1024, len(html.encode("utf-8")) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
