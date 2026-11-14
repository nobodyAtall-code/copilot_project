#!/usr/bin/env bash
# Real product VINTF build validation on an existing synced Mist LineageOS 23.2 tree.
# check-vintf-all checks generated manifests/matrices, not just XML syntax.
set -Eeo pipefail
ROOT="${1:-$HOME/android/lineage}"
ROOT="$(cd "$ROOT" && pwd)"
REPORT="$ROOT/mist-vintf-build-report.txt"
exec > >(tee "$REPORT") 2>&1
echo '===== MIST VINTF BUILD VALIDATION ====='
echo "Workspace: $ROOT"
cd "$ROOT"
test -f build/envsetup.sh || { echo 'ERROR: missing Lineage source'; exit 1; }
test -f device/xiaomi/mist/BoardConfig.mk || { echo 'ERROR: missing Mist device tree'; exit 1; }
test -f vendor/xiaomi/mist/mist-vendor.mk || { echo 'ERROR: missing Mist vendor tree'; exit 1; }
echo '===== PRODUCTION CHECKOUT REVISIONS ====='
for d in device/xiaomi/mist vendor/xiaomi/mist; do
  git -C "$d" rev-parse --short HEAD || :
  git -C "$d" status --short || :
done
echo '===== SELECT PRODUCT ====='
source build/envsetup.sh
if ! lunch lineage_mist-bp4a-userdebug; then
  lunch lineage_mist-userdebug
fi
echo '===== ACTUAL VINTF METADATA/COMPATIBILITY BUILD ====='
set +e
m -j2 check-vintf-all
result=$?
set -e
echo "===== CHECK-VINTF-ALL EXIT STATUS: $result ====="
if [ "$result" -ne 0 ]; then
  echo '===== VINTF ERROR EXCERPTS ====='
  grep -nEi -C 4 'error:|FAILED:|incompatib|checkvintf|duplicate|could not|cannot fetch|missing|not declared' "$REPORT" | tail -n 220 || :
fi
echo "===== REPORT PATH: $REPORT ====="
exit "$result"
