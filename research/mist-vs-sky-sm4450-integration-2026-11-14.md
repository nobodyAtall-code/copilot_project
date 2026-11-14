# Mist versus Sky SM4450 source-backed integration matrix

**Scope:** Comprehensive first-pass cross-device reference, not a bootable device tree, not approval to copy Sky blobs. Stock Mist = OS3.0.304.0.WPUMIXM (Android 16).

**References:** [Sky device, branch 16](https://github.com/sm4450-development/device_xiaomi_sky/tree/16), [Sky vendor, branch 16](https://github.com/sm4450-development/vendor_xiaomi_sky/tree/16), [stock Mist configs](https://github.com/nobodyAtall-code/copilot_project/blob/main/research/generated/mist-stock-config.json), [Mist stock membership](https://github.com/nobodyAtall-code/copilot_project/blob/main/research/generated/mist-archive-membership.json).

## Baseline incompatibility

Both Sky and Mist identify Qualcomm `parrot`/SM4450. Sky's README records shipping Android 13; its `BoardConfig.mk` selects kernel 5.10, super size `6979321856`, ext4 vendor, and SKU `ravelin`. Mist source evidence records stock Android 16, module release 6.6.118, super size `10200547328` and EROFS logical partitions. Sky's kernel, proprietary files, fstab, VINTF HIDL versions, SELinux paths, OTA partition sizes and audio/fingerprint code **must not** be transplanted into Mist.

## All major subsystems examined against existing offline Mist stock data

| Subsystem | Matching stock init files | Matching VINTF files | Matched executable references present / total | Mist disposition |
|---|---:|---:|---:|---|
| RIL / IMS | 4 | 16 | 9/11 | qcrilNrd exists; not integrated |
| Audio | 3 | 6 | 31/31 | audiohalservice.qti exists; not integrated |
| Camera | 1 | 2 | 1/1 | Provider selected; components not yet integrated |
| Display / GPU | 6 | 5 | 7/7 | Composer selected; graphics dependencies pending |
| Sensors | 6 | 3 | 5/5 | Stock retained, platform multihal binary selected |
| Fingerprint | 1 | 3 | 1/1 | ODM service exists; not integrated |
| Wi-Fi | 5 | 12 | 5/6 | Dependency / runtime ownership unresolved |
| Bluetooth | 1 | 4 | 1/1 | Dependency / runtime ownership unresolved |
| GNSS | 1 | 3 | 1/1 | Dependency / runtime ownership unresolved |
| Security | 4 | 4 | 3/4 | KeyMint/QSEE selected; runtime closure unproven |
| Power / USB | 5 | 4 | 5/5 | Power selected; USB owner requires reconciliation |
| Health / Thermal | 5 | 3 | 3/3 | Dependency / runtime ownership unresolved |

Counts are **filename/name matches**, not proof that a HAL is operational. Shared namespace files can be counted in multiple rows.

## Specific Mist-first component mappings

| Component | Observed stock source | Implementation decision |
|---|---|---|
| Radio | `vendor_a/etc/init/qcrilNrd.rc` and `/vendor/bin/hw/qcrilNrd` | Must use Mist stock RIL plus its exact Android 16 AIDL/IMS dependencies, not Sky's older HAL configuration |
| Audio | `vendor_a/etc/init/audiohalservice_qti.rc` and `/vendor/bin/hw/audiohalservice.qti` | Preserve Mist AIDL version and exact audio policy/DSP calibration; Sky's HIDL 7.0 configuration mismatches |
| Fingerprint | `vendor_a/etc/init/fingerprint-odm.rc` and `/vendor/bin/hw/android.hardware.biometrics.fingerprint-service.odm` | Mist ODM service differs from Sky Xiaomi fingerprint implementation |
| Wi-Fi | `vendor_a/etc/init/android.hardware.wifi-service.rc` | Verify ownership against already built LineageOS service before installing stock |
| Display | `vendor_a/etc/init/vendor.qti.hardware.display.allocator-service.rc`, plus existing composer path | Respect existing Qualcomm modules, check collisions and linker closure |
| USB | `vendor_a/etc/init/android.hardware.usb-service.qti.rc` | Verify platform ownership and exact USB configuration |
| Camera | `vendor_a/etc/init/vendor.qti.camera.provider-service_64.rc` | Provider already selected; many camera components and calibration files remain absent |

## Actual integration constraints

- Existing device/vendor Soong rules reference 42 proprietary files and the extraction manifest now matches these 42/42; that is **not** the full stock archive or dependency closure.
- `m -j2 nothing` has passed in the user's existing local LineageOS checkout after duplicate sensors/vibrator rules were corrected, but does not prove link closure, image assembly or boot.
- Before production publication, inspect all selected Mist stock init, VINTF, binaries, recursive ELF edges and local platform target owners **in one comprehensive batch**, then commit coordinated device + vendor changes. Do not silently add guessed stock libraries or duplicate platform services.
- Keep Mist's stock kernel, vendor_boot and DTBO until source and ABI, ramdisk bootconfig, verified boot and partition metadata are resolved. Do not use Sky's kernel 5.10, partition sizes, AVB values or device-specific sepolicy.

## Not completed by this comparison

RIL/IMS, audio, camera components, fingerprint, Wi-Fi, graphics allocator/DRM, full linker namespace closure, VINTF, SELinux, dynamic OTA/AVB, boot validation. Referencing Sky supplies patterns; it does not magically supply Mist firmware or validation.
