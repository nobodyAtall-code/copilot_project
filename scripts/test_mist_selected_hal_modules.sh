#!/usr/bin/env bash
# Targeted mist HAL compile/link smoke test; no ROM/OTA/image target.
# Run from ~/android/lineage. Stops immediately on the first failed stage.
# LineageOS envsetup and its m/lunch functions use variables that may be unset.
# Explicitly DISABLE nounset: Bash can inherit -u via exported SHELLOPTS
# even when this script does not enable it. Preserve errexit and pipefail.
set +u
set -eo pipefail

if [[ ! -f build/envsetup.sh || ! -f device/xiaomi/mist/BoardConfig.mk ]]; then
  echo "ERROR: run from your LineageOS root with mist device tree synced." >&2
  exit 2
fi

log_dir="${MIST_TEST_LOG_DIR:-$PWD/mist-hal-logs}"
mkdir -p "$log_dir"

# m is a function from envsetup.sh, available within this script's shell.
source build/envsetup.sh >/dev/null
lunch lineage_mist-bp4a-userdebug >/dev/null

run_stage() {
  local stage="$1"
  shift
  local file="$log_dir/${stage}.log"
  printf '\n===== %s =====\n' "$stage"
  printf 'Modules: %s\n' "$*"
  printf 'Log: %s\n' "$file"
  # Do not hide the actual status behind tee; pipefail is enabled.
  if m -j2 "$@" 2>&1 | tee "$file"; then
    echo "PASS: $stage"
  else
    echo "FAIL: $stage; stop here, do not rebuild or continue." >&2
    echo "Last 70 log lines:" >&2
    tail -n 70 "$file" >&2
    exit 1
  fi
}

# Only modules known to be present in the selected production graph.
# First stage tests source-verified stock RIL files and initial integration.
run_stage 01-radio-stock \
  mist_stock_radio \
  mist_stock_radio_script \
  mist_stock_radio_rc

# These are platform-owned modules identified by the prior installs Make graph.
# Build them rather than re-introducing duplicate Xiaomi prebuilt install rules.
run_stage 02-audio-platform audiohalservice.qti
run_stage 03-thermal-platform android.hardware.thermal-service.qti
run_stage 04-composer-platform vendor.qti.hardware.display.composer-service

# Existing vendor prebuilt camera and lights: targeted source package checks.
run_stage 05-camera-lights-stock \
  mist_stock_core_camera \
  mist_stock_core_lights

echo
echo "All targeted HAL stages passed. Runtime ELF, VINTF, SEPolicy and boot remain unverified."
echo "No full ROM, recovery, boot image, or OTA target has been built."
