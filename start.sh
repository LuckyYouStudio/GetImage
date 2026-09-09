#!/bin/sh
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then exec python3 proxy.py "$@"; fi
if command -v python  >/dev/null 2>&1; then exec python  proxy.py "$@"; fi
echo "没找到 Python。请先安装 Python 3.7+"
exit 1
