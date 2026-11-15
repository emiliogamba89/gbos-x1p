#!/usr/bin/env bash
set -u
sleep "${1:-0}"
grep -aE "zygote|surfaceflinger|bootanim|apexd.status|sys.init.updatable|apex.*failed|Parse.*error|avc:.*denied" /home/zero89/qemu-serial-live.log | tail -70
