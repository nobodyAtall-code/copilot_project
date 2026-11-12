# Mist stock extraction audit — run 43174896778

Date: 2026-11-12 UTC; source: **Global HyperOS OS3.0.304.0.WPUMIXM**, Android 16. 
Run: https://github.com/nobodyAtall-code/copilot_project/actions/runs/43174896778
Head: `74ef57a07971aaab65095af1a76d1fcf3a9fef3d`.
Status: **SUCCESS**. All mandatory steps, including stock vendor source and boot-chain staging, succeeded. Raw logical partition upload was intentionally skipped.

## Verified artifacts (expire 2026-11-26 UTC)

| Artifact | ID | ZIP size (bytes) |
| --- | ---: | ---: |
| research | 13923423842 | 289196 |
| all-so | 13923129711 | 443962342 |
| vendor-source | 13923059799 | 466442771 |
| boot-images | 13924356647 | 339752592 |

The research ZIP was downloaded and its inventories inspected. The binary archive contents have **not** yet been individually verified.

## Research ZIP observations

* Verified extracted/mounted filesystems: `mi_ext_a`, `odm_a`, `product_a`, `system_a`, `system_dlkm_a`, `system_ext_a`, `vendor_a`, `vendor_dlkm_a` — all reported EROFS.
* `summary.txt`: 11,313 indexed files; 3,030 shared libraries/symlinks.
* `candidate-summary.txt`: 3,539 **review candidates**, 42 exclusions; vendor source staging includes `vendor_a`, `odm_a`, `vendor_dlkm_a`, and `system_dlkm_a`.
* `vendor_a`: 3,129 entries, including 1,409 under `lib64`, 1,051 under `etc`, 462 under `bin`, 81 under `firmware`. Contains 89 `etc/vintf/` entries, 131 `etc/init/` entries, `etc/fstab.default` and `etc/fstab.emmc`.
* `odm_a`: 452 entries, including 18 under `etc/vintf/`, 12 under `etc/init/` and 32 under `etc/permissions/`.
* `vendor_dlkm_a`: 278 entries, of which 273 are under `lib/modules/`.
* `system_dlkm_a`: 213 entries, including 110 under `lib/modules/`; module path records `6.6.118-android15-8-g666ad52b8230-ab15657065-4k`.
* `super-metadata.txt` says 16 metadata partitions, 8 extents and 8 extracted populated partitions but **does not give dynamic partition group size limits**. Do not derive `BOARD_SUPER_PARTITION_SIZE` or group limits from extracted image sizes.

Logical image **file sizes** (these are not dynamic-group capacities):

| Image | Bytes |
| --- | ---: |
| mi_ext_a.img | 1108955136 |
| odm_a.img | 17195008 |
| product_a.img | 3339325440 |
| system_a.img | 719495168 |
| system_dlkm_a.img | 15286272 |
| system_ext_a.img | 637571072 |
| vendor_a.img | 669220864 |
| vendor_dlkm_a.img | 26017792 |

Stock boot-chain SHA256 checksums from research artifact:

```text
45ba1fec1fbacb06c182f546d63b5a4b2bf54627094745bff5e208eb72b1b579  boot.img
2030334cc0a778389732cc1e7d05d4cdf5d8c2c0ce6b281331128f2cfc847703  dtbo.img
0ee70e2a65598028e2de2b89b9b4af39422ffce40ac8283787435e91cb570989  init_boot.img
319db0e4eaaeaddc532a321d485092aac36122a78b207d3cdb39d89ac7133a17  recovery.img
813358d77d8d57b4e40e07b489df47282d11f5a0afd1d6dc7adb68db20d9ab76  vbmeta.img
1cf465b814024e2bd1df43455a51587fe6cf9f0b5535e8e13ee961b28c259377  vbmeta_system.img
f0d692792cacff3026876edbd68aed5d23be7e1acef3e6028ccd5fff21ae5acb  vendor_boot.img
```

## Concrete bring-up gates

1. Review source archive contents and link/copy preservation, `vendor/etc/vintf` and `odm/etc/vintf`, service RC files, `fstab.default` and `fstab.emmc`; cross-check with Android 16 Lineage build expectations.
2. Compare stock `vendor_dlkm` and `system_dlkm` module dependency, load and block lists to stock boot/vendor_boot ramdisk and the `mist` kernel source build configuration. Stock module ABI compatibility must be tested; do not substitute modules from `sky`.
3. Generate a **curated** `proprietary-files.txt` only after distinguishing required HAL/firmware/config from HyperOS-specific apps and testing ELF dependencies. The 3,539-item review list is explicitly not an approved production manifest. Note: `vendor/app` exclusions can include services needed for telephony or Wi-Fi calling, and should be assessed individually.
4. Obtain actual `lpdump` group capacity and block-device metadata before declaring dynamic partition BoardConfig values. Inspect init boot, vendor_boot, dtbo and recovery prior to kernel-prebuilt integration.
5. Keep device/vendor/kernel repos clean and on `main`; put research automation only in `copilot_project`. `GH_PAT` existence does not imply tested publisher permissions.

## Current production repository state at audit

* `android_device_xiaomi_mist`: six preliminary files on `main`, **not build-ready**.
* `proprietary_vendor_xiaomi_mist`: empty.
* `android_device_xiaomi_mist-kernel`: empty.
* `android_kernel_xiaomi_mist`: populated kernel source, 6.6.118 baseline.

Do not flash based on this report; no full LineageOS 23.2 build or hardware boot has been verified.
