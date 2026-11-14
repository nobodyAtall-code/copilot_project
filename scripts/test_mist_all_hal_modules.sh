#!/usr/bin/env bash
# Mist Android 16 / LineageOS 23.2 sequential HAL smoke test.
# Run once from the LineageOS root; writes ONE report with stage outcomes
# and detailed per-stage logs. Does not compile a full ROM or flash anything.
# Does NOT modify source, sync repos, repair failures, or monitor CI.
set +u
set -o pipefail

if [[ ! -f build/envsetup.sh || ! -f device/xiaomi/mist/BoardConfig.mk ]]; then
  echo "ERROR: run from the mist LineageOS root (e.g. ~/android/lineage)." >&2
  exit 2
fi

if [[ ! -f kernel/xiaomi/mist/Makefile ]]; then
  echo "ERROR: missing kernel/xiaomi/mist/Makefile; cannot produce UAPI." >&2
  exit 3
fi

ROOT="$PWD"
DEST="${MIST_HAL_REPORT_DIR:-$HOME/mist-hal-batch}"
mkdir -p "$DEST" || exit 2
RUN="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT="$DEST/mist-hal-all-tests-$RUN.txt"
LOGS="$DEST/logs-$RUN"
mkdir -p "$LOGS" || exit 2

# Android envsetup / lunch may contain unset variable references.
source build/envsetup.sh >"$LOGS/00-envsetup.log" 2>&1
source_rc=$?
if (( source_rc != 0 )); then
  echo "envsetup failed ($source_rc), see $LOGS/00-envsetup.log" >&2
  exit "$source_rc"
fi
lunch lineage_mist-bp4a-userdebug >"$LOGS/00-lunch.log" 2>&1
lunch_rc=$?
if (( lunch_rc != 0 )); then
  echo "lunch failed ($lunch_rc), see $LOGS/00-lunch.log" >&2
  exit "$lunch_rc"
fi

printf 'Mist LineageOS 23.2 targeted HAL batch test\n' >"$REPORT"
printf 'Started UTC: %s\nRoot: %s\nReport: %s\nLogs: %s\n' "$(date -u -Is)" "$ROOT" "$REPORT" "$LOGS" >>"$REPORT"
printf 'Kernel: stock prebuilt (forced); source tree used for UAPI only\n' >>"$REPORT"
printf 'Validation scope: source compilation/link/copy only, NOT hardware boot/runtime\n\n' >>"$REPORT"

pass_count=0
fail_count=0
declare -a RESULTS=()

# Intentionally continue after a stage failure to collect as many
# independent failures as possible. A dependent target may also fail.
run_stage() {
  local name="$1"
  shift
  local file="$LOGS/$name.log"
  local status
  printf '\n==> %s: %s\n' "$name" "$*"
  m -j2 "$@" >"$file" 2>&1
  status=$?
  if (( status == 0 )); then
    RESULTS+=("PASS | $name | $*")
    ((pass_count+=1))
    echo "PASS: $name"
  else
    RESULTS+=("FAIL(exit $status) | $name | $*")
    ((fail_count+=1))
    echo "FAIL(exit $status): $name (continuing)"
  fi

  {
    echo
    echo "================================================================"
    echo "STAGE: $name | EXIT: $status"
    echo "MODULES: $*"
    echo "LOG: $file"
    echo "---- Error / failure indicators (max 55 lines) ----"
    grep -nE '(^FAILED:|^ninja:|error:|fatal error:|^make: \*\*\*|^#### failed|^error:|undefined reference|not found|does not exist|Killed)' "$file" | head -55 || true
    echo "---- Final 65 lines ----"
    tail -n 65 "$file"
  } >> "$REPORT"
}

# Known targets from scripts/test_mist_selected_hal_modules.sh, plus
# the successful MiCode display-UAPI header generator.
run_stage 01-display-uapi qti_generate_display_kernel_headers
run_stage 02-radio-stock mist_stock_radio mist_stock_radio_script mist_stock_radio_rc
run_stage 03-audio-platform audiohalservice.qti
run_stage 04-thermal-platform android.hardware.thermal-service.qti
run_stage 05-display-composer vendor.qti.hardware.display.composer-service
run_stage 06-camera-lights-stock mist_stock_core_camera mist_stock_core_lights

{
  echo
  echo "================================================================"
  echo "SUMMARY"
  printf '%s\n' "${RESULTS[@]}"
  echo "Passed stages: $pass_count"
  echo "Failed stages: $fail_count"
  echo "Finished UTC: $(date -u -Is)"
  echo "WARNING: all-pass does not establish ELF/VINTF/SEPolicy/kernel ABI or device boot success."
  echo "NO full ROM or flash attempted."
} >> "$REPORT"

echo
printf '%s\n' "${RESULTS[@]}"
echo "DONE: $pass_count passed, $fail_count failed"
echo "SEND ONLY THIS TXT: $REPORT"
echo "Detailed individual logs preserved: $LOGS"
if (( fail_count != 0 )); then exit 1; fi
exit 0
