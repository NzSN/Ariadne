#!/usr/bin/env bash
set -euo pipefail
OUT=/d/Desktop/Workspaces/Ariadne-repin-79938-20261010
mkdir -p "$OUT"
CDB='/c/Program Files/WindowsApps/Microsoft.WinDbg_1.2606.22001.0_x64__8wekyb3d8bbwe/amd64/cdb.exe'
export MSYS2_ARG_CONV_EXCL='*'
"$CDB" -z D:/Services/dump-ledger-runtime/data/vault/dump_79938FAE443F4021A4F7B6C215/original.dmp -y 'SRV*d:\symcache-dump79938-20261008*https://192.168.150.219:4080/symbols' -c '!lmi lceda_pro; .ecxr; r; x lceda_pro!*TranslatedFrame*AdvanceIterator*; u 00007ff63cba6c50 00007ff63cba6cae; .fnent 00007ff63cba6c50; q' > "$OUT/entry-witness.log" 2>&1
