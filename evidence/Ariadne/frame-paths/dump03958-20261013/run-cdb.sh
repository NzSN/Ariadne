#!/bin/bash
set -euo pipefail
output=/d/Desktop/Workspaces/dump_03958DA4FCA844A786262A1053/frame-paths-20261013
mkdir -p "$output"
cdb.exe -z 'D:/Services/dump-ledger-runtime/data/vault/dump_03958DA4FCA844A786262A1053/original.dmp' -y 'SRV*d:\symcache-dump03958-20261009*https://192.168.150.219:4080/symbols' -cf 'D:/ariadne-frame-paths-dump03958-20261013.cmd' > "$output/cdb-frames.log" 2>&1
sha256sum "$output/cdb-frames.log"
