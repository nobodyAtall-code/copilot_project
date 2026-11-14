#!/usr/bin/env bash
# Real Android policy compile and neverallow validation; run in Lineage checkout.
set -Eeo pipefail
# Android envsetup.sh/lunch reference optional unset variables (e.g. TOP).
# Do not use nounset (-u) when sourcing Android's build shell functions.
ROOT="$HOME/android/lineage"
if [ -n "${1:-}" ]; then ROOT="$1"; fi
MIST_SEPOLICY_REPORT="$ROOT/mist-selinux-compile-report.txt"
mkdir -p "$ROOT"
exec > >(tee "$MIST_SEPOLICY_REPORT") 2>&1
echo "===== MIST SELINUX COMPILE ====="
cd "$ROOT"
test -f build/envsetup.sh || { echo "ERROR: not LineageOS source"; exit 1; }
test -f device/xiaomi/mist/sepolicy/vendor/mist_qseecom.te || { echo "ERROR: update device tree from main first"; exit 1; }
git -C device/xiaomi/mist log -1 --format='%h %s'
git -C device/xiaomi/mist status --short
df -h .
source build/envsetup.sh
if ! lunch lineage_mist-bp4a-userdebug; then lunch lineage_mist-userdebug; fi
set +e
m -j2 selinux_policy
status=$?
set -e
echo "===== COMPILE EXIT STATUS: $status ====="
if [ "$status" -ne 0 ]; then
  grep -nEi -C 4 'error:|neverallow|unknown type|unknown class|duplicate declaration|invalid.*context|failed' "$MIST_SEPOLICY_REPORT" | tail -n 160 || :
fi
echo "===== REPORT PATH: $MIST_SEPOLICY_REPORT ====="
exit "$status"
