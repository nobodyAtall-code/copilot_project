#!/usr/bin/env bash
# Mist Android 16 / LineageOS 23.2: reproducible, source-pinned display UAPI header integration.
# Used after repo sync. No full build/flash. Version recorded 2026-11-14.
set -euo pipefail

ROOT="${1:-$HOME/android/lineage}"
DRIVER="$ROOT/vendor/qcom/opensource/mist-display-uapi"
COMMON="$ROOT/hardware/qcom-caf/common/Android.bp"
URL="https://github.com/MiCode/vendor_opensource_display-drivers.git"
PIN="310b76de47b1a4d0c3e1e373ef1b52039f2140fd"

test -f "$ROOT/build/envsetup.sh" || { echo "ERROR: not a LineageOS checkout: $ROOT" >&2; exit 1; }
test -f "$COMMON" || { echo "ERROR: missing common Android.bp: $COMMON" >&2; exit 1; }

if [ ! -e "$DRIVER" ]; then
    mkdir -p "$(dirname "$DRIVER")"
    git clone --no-checkout --filter=blob:none "$URL" "$DRIVER"
    git -C "$DRIVER" checkout --detach "$PIN"
elif [ -d "$DRIVER/.git" ]; then
    actual="$(git -C "$DRIVER" rev-parse HEAD)"
    if [ "$actual" != "$PIN" ]; then
        echo "ERROR: local display driver commit $actual differs from tested pin $PIN; stopping" >&2
        exit 1
    fi
else
    echo "ERROR: path exists but is not a Git checkout: $DRIVER" >&2
    exit 1
fi

export MIST_DISPLAY_DRIVER="$DRIVER"
export MIST_DISPLAY_COMMON="$COMMON"
python3 - <<'PY'
from pathlib import Path
import os

driver = Path(os.environ["MIST_DISPLAY_DRIVER"])
common = Path(os.environ["MIST_DISPLAY_COMMON"])
for relative in (
    "include/uapi/display/drm/msm_drm_pp.h",
    "include/uapi/display/drm/sde_drm.h",
    "include/uapi/display/media/mmm_color_fmt.h",
    "include/uapi/display/media/msm_sde_rotator.h",
    "include/uapi/display/drm/mi_disp.h",
    "include/uapi/display/hdcp/msm_hdmi_hdcp_mgr.h",
    "display_kernel_headers.py",
):
    if not (driver / relative).is_file():
        raise SystemExit(f"ERROR: upstream header file absent: {relative}")

original = (driver / "Android.bp").read_text()
common_text = common.read_text()
module = '''cc_library_headers {
    name: "qti_display_kernel_headers",
    generated_headers: ["qti_generate_display_kernel_headers"],
    export_generated_headers: ["qti_generate_display_kernel_headers"],
    vendor: true,
    recovery_available: true
}
'''
old = '''cc_library_headers {
    name: "qti_display_kernel_headers",
    defaults: ["generated_kernel_header_defaults"],
}'''
new = '''cc_library_headers {
    name: "qti_display_kernel_headers",
    defaults: ["generated_kernel_header_defaults"],
    generated_headers: ["qti_generate_display_kernel_headers"],
    export_generated_headers: ["qti_generate_display_kernel_headers"],
}'''

# Verify all preconditions BEFORE writing either file.
if original.count(module) == 1:
    patched_driver = original.replace(module, "").rstrip() + "\n"
elif module not in original and original.count('name: "qti_generate_display_kernel_headers"') == 1 and "cc_library_headers" not in original:
    patched_driver = original  # already integrated on this machine
else:
    raise SystemExit("ERROR: unrecognized MiCode Android.bp; refusing to modify")

if old in common_text and new not in common_text and common_text.count(old) == 1:
    patched_common = common_text.replace(old, new, 1)
elif new in common_text and old not in common_text and common_text.count(new) == 1:
    patched_common = common_text
else:
    raise SystemExit("ERROR: unexpected qti_display_kernel_headers definition in CAF common")

if patched_driver != original:
    (driver / "Android.bp").write_text(patched_driver)
if patched_common != common_text:
    common.write_text(patched_common)

print("OK: pinned Mist UAPI source and header generator wired without duplicate module")
PY

echo "===== CURRENT LOCAL PATCHES ====="
git -C "$DRIVER" diff --check
git -C "$ROOT/hardware/qcom-caf/common" diff --check
git -C "$DRIVER" diff -- Android.bp
git -C "$ROOT/hardware/qcom-caf/common" diff -- Android.bp
echo "NEXT: cd '$ROOT'; source build/envsetup.sh; lunch lineage_mist-bp4a-userdebug"
echo "THEN: m -j2 qti_generate_display_kernel_headers"
echo "NOTE: targeted Display HAL has NOT been proven to compile or boot."
