# Mist stock firmware extraction — verified run 43172012149

**Status:** successful, checked against GitHub Actions job 131027326783 on 2026-11-12.

- Target: HyperOS OS3.0.304.0.WPUMIXM (Android 16), Redmi Note 17 5G (`mist`)
- Full fastboot firmware MD5 passed: `c4450c4e168052ca9de1211306d3beff`
- Super image: converted from Android sparse to raw.
- Super metadata: format v10.2, 16 partition entries, eight populated partitions in the extracted slot.
- Eight mounted partitions: `odm_a`, `product_a`, `system_a`, `system_dlkm_a`, `system_ext_a`, `vendor_a`, `vendor_dlkm_a`, `mi_ext_a`.
- All eight identified/mounted as EROFS.
- Indexed files: **11,313**.
- Shared libraries and symlinks: **3,030**.
- Compressed shared-library content: **443,962,172 bytes**.
- Entire run: success.

## GitHub Actions artifacts (expire 2026-11-26 UTC)

- Research/inventories: https://github.com/nobodyAtall-code/copilot_project/actions/runs/43172012149/artifacts/13922199120
- All shared libraries: https://github.com/nobodyAtall-code/copilot_project/actions/runs/43172012149/artifacts/13923290333

## Important limitations

- The **.so archive is NOT a complete proprietary vendor tree**. It does not include all required executables, configuration files, firmware, permission XMLs, .ko modules, HAL service init files or other assets.
- Full file inventory is an inventory, not a reviewed `proprietary-files.txt`.
- Physical images (`vendor_boot`, `boot`, `init_boot`, `recovery`, `dtbo`, firmware images) were not unpacked into their component ramdisks or device trees by this workflow.
- `lpunpack` printed basic metadata and partition names. Full group sizes, actual slot metadata and partition attributes still need a dedicated `lpdump` analysis before generating `BoardConfig.mk`.
- SHA256 of artifact ZIP is distinct from the firmware MD5.
- GitHub Actions artifacts are temporary, not a permanent storage location.

## Next production stage

1. Inspect the exact entries in the research artifact, particularly `all-files.tsv`, `libraries.tsv` and `super-metadata.txt`.
2. Select required stock blobs across all relevant partitions, preserving relative paths, executable modes, symlinks, and ELF dependencies.
3. Extract the boot/vendor_boot ramdisks and kernel modules; compare with stock init and fstab.
4. Build minimal, reviewable `android_device_xiaomi_mist` and `proprietary_vendor_xiaomi_mist` trees on `main`, following the SM4450 project's structural patterns, but not copying its device-specific data.
5. Validate LineageOS 23.2 build then tackle hardware bring-up.
