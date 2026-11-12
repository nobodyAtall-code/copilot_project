# Mist 2026-11-13 — independent LP allocations and stock boot-header audit

**Scope:** Read-only checks against stock Xiaomi Global `OS3.0.304.0.WPUMIXM`. No ROM build, no successful boot, no signed-image verification and no flash readiness.

## Independent logical partition allocation check: PASSED

- [Stock super run 43265353383](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43265353383), job `131347323611`, completed **success**.
- Checked full job logs; Ubuntu Go `go1.22.2 linux/amd64` installed. Entire original fastboot firmware was downloaded and verified against MD5 `c4450c4e168052ca9de1211306d3beff`.
- Existing Python reader validated LP geometry and checksums; three metadata slots and matching primary/backup records.
- Independent pinned third-party Go reader `soe1hom-arch/lpunpack-go@073a3302a3c3ffae01633989e6dd1e60b6de15b7` returned 8 populated partition sizes. Strict comparator output: `partition_sizes_match=true`, `missing=[]`, `unexpected=[]`, `differing={}`.
- [Artifact 13967135180](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43265353383/artifacts/13967135180) contains the actual four reports; comparison JSON personally inspected, not inferred from green CI badge.

| Populated partition | Go/Python-agreed bytes |
| --- | ---: |
| `odm_a` | 17195008 |
| `product_a` | 3339325440 |
| `system_a` | 719495168 |
| `system_dlkm_a` | 15286272 |
| `system_ext_a` | 637571072 |
| `vendor_a` | 669220864 |
| `vendor_dlkm_a` | 26017792 |
| `mi_ext_a` | 1108955136 |

Python checksum-validated stock metadata still reports `qti_dynamic_partitions_a` and `qti_dynamic_partitions_b` each with maximum `10190061568` bytes, but **Go reader does not independently check group membership, maximum sizes, slot semantics or virtual A/B OTA design**. Full AOSP `lpdump` comparison remains open. Do not write stock maximum values blindly into production `BoardConfig.mk`.

## Independent boot-chain *structure* review: PASSED

- New read-only script [`scripts/inspect_mist_boot_chain.py`](../scripts/inspect_mist_boot_chain.py) and research-only [workflow](../.github/workflows/mist-stock-boot-chain-review.yml) use original SHA256-verified [run 43174896778](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43174896778) stock boot artifact.
- [Run 43266837030](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43266837030), job `131352527506`, **success**. Checked logs and parsed actual [artifact 13966113003](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43266837030/artifacts/13966113003). All seven exact boot-chain SHA256 values matched; no structure parser errors.
- `boot.img`: Android boot header v4, kernel payload **36801024** bytes at offset **4096**, ramdisk size **0**. Matches the already published verified kernel Image.
- `init_boot.img`: header v4, **2478317**-byte LZ4-legacy ramdisk, kernel size 0.
- `recovery.img`: header v4, **28157475**-byte LZ4-legacy ramdisk, kernel size 0; dedicated recovery partition.
- `vendor_boot.img`: vendor header v4, **4096** page size, **10992661**-byte LZ4-legacy vendor ramdisk, one vendor ramdisk table entry (type 1, 10992661 bytes), **4390641**-byte DTB at offset **10997760**, **204**-byte bootconfig at offset **15392768**.
- `dtbo.img`: Android DTBO table v0, **22** table entries, total table/payload span **5131075** bytes inside the stock 25165824-byte partition image.
- `vbmeta.img` and `vbmeta_system.img`: AVB0 magic and bounded auth/aux blocks parse successfully. **Signatures, descriptors, chain keys, rollback index and AVB enforcement have not been verified**.

### Production change based on these facts

- [Device BoardConfig commit 81e6bed](https://github.com/nobodyAtall-code/android_device_xiaomi_mist/commit/81e6bed4685e4557a83b8e5d9ab5d98047846305) on existing `main`: explicitly sets `BOARD_INIT_BOOT_HEADER_VERSION := 4`, `BOARD_MKBOOTIMG_INIT_ARGS += --header_version $(BOARD_INIT_BOOT_HEADER_VERSION)`, and `BOARD_RAMDISK_USE_LZ4 := true`.
- No fabricated DTB, proprietary file, AVB key, or guessed group size was added. Kernel/vendor trees were not changed by this milestone.
- These settings reflect observed stock structure and LineageOS 23.2 conventions; **they have not yet passed a full LineageOS build**.

## Next gates

1. Independently corroborate group maxima/membership and A/B OTA semantics with official AOSP `lpdump` or a trusted stock-device dump; engineering-review `mi_ext` before adding dynamic groups to production.
2. Extract *verified stock* vendor_boot DTB and DTBO metadata and examine matching DTBs/overlays; do not assume 22 DTBO entries mean they all apply to this SKU. Review ramdisk modules/load order and bootconfig without publishing personal identifiers.
3. Inspect AVB descriptors and chained keys, VINTF and SELinux, plus curated HAL library dependencies.
4. Once verified: complete production device/kernel/vendor packaging, run `lunch lineage_mist-...-userdebug` using correct 23.2 release config, build and debug. No flashable image has been produced.
