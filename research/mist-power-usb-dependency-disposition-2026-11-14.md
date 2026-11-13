# Mist Power/USB dependency disposition — 14 November 2026

## Evidence

- User-supplied [run 43528147095](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43528147095/job/132238899844) completed successfully, based on [run 43527718972](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43527718972) and the live vendor/device trees.
- Unique stock-resolved library paths: **10**; **0** already listed in the current device `proprietary-files.txt`; **6** unique unresolved SONAMEs.
- Reconciliation [artifact 14085952830](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43528147095/artifacts/14085952830).
- These are **archive stock file candidates**, not 10 proven missing runtime dependencies. A source AIDL library, platform VNDK runtime or APEX may supply an ABI-equivalent output. Do not indiscriminately install them.

## Runtime dependency classification

| Stock library name | Initial engineering disposition |
|---|---|
| `android.hardware.common-V2-ndk.so` | Check generated Android 16 AIDL platform/vendor module output, exact VINTF / ABI |
| `android.hardware.common.fmq-V1-ndk.so` | Check generated AIDL / FMQ implementation ownership |
| `android.hardware.power-V5-ndk.so` | Check AIDL NDK version-specific platform output and existing vendor install path |
| `android.hardware.usb-V1-ndk.so` | Check AIDL NDK version-specific platform output and existing vendor install path |
| `libbase.so` | Android platform library: **do not blindly copy from stock** |
| `libc++.so` | Android platform/vendor runtime: **do not blindly copy from stock** |
| `libcutils.so` | Android platform library: **do not blindly copy from stock** |
| `libfmq.so` | Android hardware/platform library: **do not blindly copy from stock** |
| `libutils.so` | Android platform library: **do not blindly copy from stock** |
| `libxml2.so` | Check LineageOS vendor availability and exact namespace/ABI; only vendor-copy if proven required |

Stock-unresolved SONAMEs: `libbinder_ndk.so`, `libc.so`, `libdl.so`, `liblog.so`, `libm.so`, `libvndksupport.so`. They must be checked in Android 16 platform/APEX and vendor linker namespaces; do **not** label them missing firmware blobs.

## Next implementation gate

1. In the user's existing LineageOS 23.2 checkout, sync the latest production vendor/device `main` branches.
2. Run the **short** `source build/envsetup.sh && lunch lineage_mist-bp4a-userdebug && m -j2 nothing` module graph/Kati test, **not a full ROM**. Capture the first actual duplicate installation target or unresolved Soong dependency, if any. This is necessary because source archive and GitHub repo alone cannot prove whether the same binary path is built by LineageOS.
3. Verify `vendor_boot` first-stage ramdisk, init fstab placement, avb key paths and kernel-module load order before enabling the staged `fstab.mist` or claiming boot readiness.
4. On actual identified platform/library gaps, publish only strictly necessary reviewed files and their extraction entries; do not install whole stock runtime blindly.

Production commits already verified: vendor [3446338](https://github.com/nobodyAtall-code/proprietary_vendor_xiaomi_mist/commit/3446338), device [41666b8](https://github.com/nobodyAtall-code/android_device_xiaomi_mist/commit/41666b8). No new production binaries are automatically approved by this report.
