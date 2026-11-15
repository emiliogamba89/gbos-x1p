#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
n=$(grep -n "cjk_bytes = (b" system_port.py | head -n1 | cut -d: -f1)
echo "riga BUILD: $n"
sed -n "$((n - 2)),$((n + 4))p" system_port.py | od -c
n2=$(grep -n "cjk_bytes" system_port.py | grep -n "assert cat" | head -n1 | cut -d: -f1)
echo "riga VERIFY: $n2"
sed -n "$((n2 - 1)),$((n2 + 1))p" system_port.py | od -c
