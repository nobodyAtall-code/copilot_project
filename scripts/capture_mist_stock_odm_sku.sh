#!/usr/bin/env bash
# Read-only stock-device evidence for Mist ODM radio SKU variant.
# Does NOT dump serials, IMEI, subscriber identifiers or personal data.
set -Eeo pipefail
OUT="${1:-mist-odm-sku-evidence.txt}"
command -v adb >/dev/null || { echo "adb unavailable"; exit 1; }
adb get-state | grep -qx device || { echo "Connect an authorized booted stock Mist via adb"; exit 1; }
{
  echo '# Mist ODM radio SKU evidence (non-identifying values)'
  for key in ro.boot.product.vendor.sku ro.boot.product.hardware.sku ro.boot.hardware.sku persist.radio.multisim.config persist.vendor.radio.multisim.config ro.product.vendor.device ro.build.version.release ro.boot.slot_suffix; do
    case "$key" in ro.boot.slot_suffix) continue ;; esac
    val="$(adb shell getprop "$key" | tr -d '\r' | head -c 160)"
    printf '%s=%s\n' "$key" "$val"
  done
  echo '# ODM VINTF manifest files selected on stock (paths only)'
  adb shell 'for p in /odm/etc/vintf/manifest.xml /odm/etc/vintf/manifest/*.xml; do [ -f "$p" ] && echo "$p"; done' | tr -d '\r'
} | tee "$OUT"
echo "Saved: $OUT"
