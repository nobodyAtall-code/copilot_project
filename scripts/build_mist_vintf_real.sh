#!/usr/bin/env bash
# Real Mist LineageOS 23.2 VINTF build gate against an EXISTING synced workspace.
# No full ROM build, firmware download, upload of blobs, AVB changes or flash.
set -Eeo pipefail
# Bash may inherit nounset via SHELLOPTS/BASHOPTS from user's environment.
# Android build/envsetup.sh references optional TOP before assigning it.
# IMPORTANT: Android lunch also overwrites OUT. Never name report variable OUT.
set +u
GATE_VERSION="mist-vintf-live-output-v5-20261115"
ROOT="${1:-$HOME/android/lineage}"
ROOT="$(cd "$ROOT" && pwd)"
MIST_VINTF_REPORT_PATH="$ROOT/mist-vintf-build-report.txt"
MIST_VINTF_RESULT_PATH="$ROOT/mist-vintf-build-result.json"
MIST_VINTF_BUILD_TRACE_PATH="$ROOT/mist-vintf-build-ninja-log.txt"
mkdir -p "$(dirname "$MIST_VINTF_REPORT_PATH")"
: > "$MIST_VINTF_REPORT_PATH"
: > "$MIST_VINTF_BUILD_TRACE_PATH"
record() {
  local status="$1" lunch_name="$2" fail_stage="$3"
  RESULT_JSON="$MIST_VINTF_RESULT_PATH" RESULT_STATUS="$status" RESULT_LUNCH="$lunch_name" RESULT_STAGE="$fail_stage" \
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
echo "===== REAL MIST VINTF GATE (no ROM build) =====" | tee -a "$MIST_VINTF_REPORT_PATH"
echo "Launcher version: $GATE_VERSION; shell flags: $-" | tee -a "$MIST_VINTF_REPORT_PATH"
echo "Workspace: $ROOT" | tee -a "$MIST_VINTF_REPORT_PATH"
cd "$ROOT"
if [[ ! -f build/envsetup.sh || ! -f device/xiaomi/mist/BoardConfig.mk || ! -f vendor/xiaomi/mist/mist-vendor.mk ]]; then
  echo "ERROR: local Lineage/device/vendor source missing" | tee -a "$MIST_VINTF_REPORT_PATH"
  record BLOCKED "" missing_checkout
  exit 2
fi
DEVICE_SHA="$(git -C device/xiaomi/mist rev-parse HEAD 2>/dev/null || true)"
VENDOR_SHA="$(git -C vendor/xiaomi/mist rev-parse HEAD 2>/dev/null || true)"
printf 'device %s\nvendor %s\n' "$DEVICE_SHA" "$VENDOR_SHA" | tee -a "$MIST_VINTF_REPORT_PATH"
echo "===== PRODUCT SELECTION =====" | tee -a "$MIST_VINTF_REPORT_PATH"
# Reassert before Android setup in case a sourced/interactive shell changed options.
set +u
if ! source build/envsetup.sh >> "$MIST_VINTF_REPORT_PATH" 2>&1; then
  echo "ERROR: Android envsetup.sh failed; review report" | tee -a "$MIST_VINTF_REPORT_PATH"
  record BLOCKED "" envsetup
  exit 2
fi
set +u
LUNCH_NAME="lineage_mist-bp4a-userdebug"
if lunch "$LUNCH_NAME" >> "$MIST_VINTF_REPORT_PATH" 2>&1; then
  :
else
  echo "ERROR: expected LineageOS 23.2 lunch unavailable: $LUNCH_NAME" | tee -a "$MIST_VINTF_REPORT_PATH"
  record BLOCKED "$LUNCH_NAME" lunch
  exit 2
fi
echo "===== BUILD TARGET: check-vintf-all (live output, not full ROM) =====" | tee -a "$MIST_VINTF_REPORT_PATH"
set +e
m -j2 check-vintf-all 2>&1 | tee "$MIST_VINTF_BUILD_TRACE_PATH"
RC=${PIPESTATUS[0]}
set -e
cat "$MIST_VINTF_BUILD_TRACE_PATH" >> "$MIST_VINTF_REPORT_PATH"
printf '\ncheck-vintf-all exit: %s\n' "$RC" | tee -a "$MIST_VINTF_REPORT_PATH"
if (( RC != 0 )); then
  echo "===== FIRST ERRORS AND BUILD CONTEXT =====" | tee -a "$MIST_VINTF_REPORT_PATH"
  grep -nEi -C 3 'FAILED:|error:|incompatib|checkvintf|duplicate|could not|cannot fetch|missing|not declared|ninja: build stopped' "$MIST_VINTF_BUILD_TRACE_PATH" | head -n 240 | tee -a "$MIST_VINTF_REPORT_PATH" || :
  record FAILED "$LUNCH_NAME" check_vintf_all
  echo "Report: $MIST_VINTF_REPORT_PATH"
  echo "MIST_VINTF_RESULT_PATH:   $MIST_VINTF_RESULT_PATH"
  exit "$RC"
fi
record PASS "$LUNCH_NAME" ""
echo "PASS: actual check-vintf-all build target completed. Runtime device/OTA not validated." | tee -a "$MIST_VINTF_REPORT_PATH"
echo "Report: $MIST_VINTF_REPORT_PATH"
echo "MIST_VINTF_RESULT_PATH:   $MIST_VINTF_RESULT_PATH"
