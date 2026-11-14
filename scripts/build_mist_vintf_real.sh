#!/usr/bin/env bash
# Real Mist LineageOS 23.2 VINTF build gate against an EXISTING synced workspace.
# No full ROM build, firmware download, upload of blobs, AVB changes or flash.
set -Eeo pipefail
# Bash may inherit nounset via SHELLOPTS/BASHOPTS from user's environment.
# Android build/envsetup.sh references optional TOP before assigning it.
set +u
GATE_VERSION="mist-vintf-nounset-v3-20261115"
ROOT="${1:-$HOME/android/lineage}"
ROOT="$(cd "$ROOT" && pwd)"
OUT="$ROOT/mist-vintf-build-report.txt"
JSON="$ROOT/mist-vintf-build-result.json"
TRACE="$ROOT/mist-vintf-build-ninja-log.txt"
mkdir -p "$(dirname "$OUT")"
: > "$OUT"
: > "$TRACE"
record() {
  local status="$1" lunch_name="$2" fail_stage="$3"
  RESULT_JSON="$JSON" RESULT_STATUS="$status" RESULT_LUNCH="$lunch_name" RESULT_STAGE="$fail_stage" \
  DEVICE_SHA="${DEVICE_SHA:-}" VENDOR_SHA="${VENDOR_SHA:-}" \
  python3 - <<'PY'
import json, os
from pathlib import Path
p=Path(os.environ["RESULT_JSON"])
p.write_text(json.dumps({
 "mode":"REAL_LINEAGE_BUILD_TARGET",
 "target":"check-vintf-all",
 "status":os.environ["RESULT_STATUS"],
 "failure_stage":os.environ["RESULT_STAGE"],
 "lunch":os.environ["RESULT_LUNCH"],
 "device_sha":os.environ["DEVICE_SHA"],
 "vendor_sha":os.environ["VENDOR_SHA"],
 "full_rom_build_performed":False,
 "on_device_hal_registration_verified":False,
 "virtual_ab_ota_verified":False,
 "custom_avb_signed_or_flashable":False,
 "notes":"A successful check-vintf-all only validates the generated build-time VINTF target. SKU-specific runtime property selection still requires device evidence."
},indent=2)+"\n")
PY
}
echo "===== REAL MIST VINTF GATE (no ROM build) =====" | tee -a "$OUT"
echo "Launcher version: $GATE_VERSION; shell flags: $-" | tee -a "$OUT"
echo "Workspace: $ROOT" | tee -a "$OUT"
cd "$ROOT"
if [[ ! -f build/envsetup.sh || ! -f device/xiaomi/mist/BoardConfig.mk || ! -f vendor/xiaomi/mist/mist-vendor.mk ]]; then
  echo "ERROR: local Lineage/device/vendor source missing" | tee -a "$OUT"
  record BLOCKED "" missing_checkout
  exit 2
fi
DEVICE_SHA="$(git -C device/xiaomi/mist rev-parse HEAD 2>/dev/null || true)"
VENDOR_SHA="$(git -C vendor/xiaomi/mist rev-parse HEAD 2>/dev/null || true)"
printf 'device %s\nvendor %s\n' "$DEVICE_SHA" "$VENDOR_SHA" | tee -a "$OUT"
echo "===== PRODUCT SELECTION =====" | tee -a "$OUT"
# Reassert before Android setup in case a sourced/interactive shell changed options.
set +u
if ! source build/envsetup.sh >> "$OUT" 2>&1; then
  echo "ERROR: Android envsetup.sh failed; review report" | tee -a "$OUT"
  record BLOCKED "" envsetup
  exit 2
fi
set +u
LUNCH_NAME="lineage_mist-bp4a-userdebug"
if lunch "$LUNCH_NAME" >> "$OUT" 2>&1; then
  :
else
  echo "ERROR: expected LineageOS 23.2 lunch unavailable: $LUNCH_NAME" | tee -a "$OUT"
  record BLOCKED "$LUNCH_NAME" lunch
  exit 2
fi
echo "===== BUILD TARGET: check-vintf-all =====" | tee -a "$OUT"
set +e
m -j2 check-vintf-all > "$TRACE" 2>&1
RC=$?
set -e
cat "$TRACE" >> "$OUT"
printf '\ncheck-vintf-all exit: %s\n' "$RC" | tee -a "$OUT"
if (( RC != 0 )); then
  echo "===== FIRST ERRORS AND BUILD CONTEXT =====" | tee -a "$OUT"
  grep -nEi -C 3 'FAILED:|error:|incompatib|checkvintf|duplicate|could not|cannot fetch|missing|not declared|ninja: build stopped' "$TRACE" | head -n 240 | tee -a "$OUT" || :
  record FAILED "$LUNCH_NAME" check_vintf_all
  echo "Report: $OUT"
  echo "JSON:   $JSON"
  exit "$RC"
fi
record PASS "$LUNCH_NAME" ""
echo "PASS: actual check-vintf-all build target completed. Runtime device/OTA not validated." | tee -a "$OUT"
echo "Report: $OUT"
echo "JSON:   $JSON"
