# Mist verified stock dynamic-partition metadata — 2026-11-12

**Status:** liblp header/tables/geometry checksums validated in local Python inspector; independent AOSP `lpdump` confirmation and OTA/layout engineering review **still pending**. This is **not** an approved LineageOS BoardConfig or a flashable product.

- Source: [GitHub Actions run 43229081227](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43229081227), job 131219592083 (success).
- Downloadable original evidence: [artifact 13949851334](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43229081227/artifacts/13949851334), containing `mist-super-metadata.json` and `firmware.md5`. No source firmware image was committed.
- Verified stock firmware: `OS3.0.304.0.WPUMIXM`, fastboot archive MD5 `c4450c4e168052ca9de1211306d3beff`.
- Raw `super` size: **10200547328 bytes** (agrees with device fastboot observation). LP block device `super` also declares 10200547328 bytes, 1048576-byte alignment, first logical sector 2048.
- LP geometry at offset 4096; maximum metadata size 65536 bytes, metadata slot count 3, logical block size 4096. LP header version **10.2**, flags integer **1**. Geometry SHA256 valid, primary/backup metadata header and table SHA256 valid. All three slots report matching primary/backup data and identical parsed layout; `integrity_checks_passed=true`.
- Explicit caution: three **metadata slots** are not three device A/B boot slots. The `_a` and `_b` names below refer to A/B logical partition groups and partitions.

## Exact group allocations from checksum-validated metadata

| Group | Maximum bytes | Allocated bytes |
|---|---:|---:|
| `default` | 0 | 0 |
| `qti_dynamic_partitions_a` | 10190061568 | 6533066752 |
| `qti_dynamic_partitions_b` | 10190061568 | 0 |

**Do not sum both A/B group maxima** as though each had its own physical `super`: metadata records separate per-slot capacity constraints within one physical partition.

## Stock logical partitions

| Logical partition | Stock allocated bytes | Group |
|---|---:|---|
| `odm_a` | 17195008 | `qti_dynamic_partitions_a` |
| `product_a` | 3339325440 | `qti_dynamic_partitions_a` |
| `system_a` | 719495168 | `qti_dynamic_partitions_a` |
| `system_dlkm_a` | 15286272 | `qti_dynamic_partitions_a` |
| `system_ext_a` | 637571072 | `qti_dynamic_partitions_a` |
| `vendor_a` | 669220864 | `qti_dynamic_partitions_a` |
| `vendor_dlkm_a` | 26017792 | `qti_dynamic_partitions_a` |
| `mi_ext_a` | 1108955136 | `qti_dynamic_partitions_a` |

Each matching `_b` partition is recorded with **0** allocated bytes and belongs to `qti_dynamic_partitions_b`. The total A-slot allocation is **6533066752** bytes. These are **stock allocations**, not minimum or appropriate LineageOS partition image sizes.

## Remaining engineering review before BoardConfig edits

1. Compare against independent AOSP `lpdump`/liblp output from this exact stock firmware or read-only on-device dump; confirm full group metadata interpretation, slot names and header flag semantics.
2. Determine the correct LineageOS 23.2 dynamic-partitions / virtual A/B OTA configuration, including whether to preserve/repackage `mi_ext`, group-size budgeting and reserve alignment. Stock group max is evidence, not an automatic BoardConfig declaration.
3. Validate stock `vendor_boot`, `init_boot`, recovery, `dtbo`, AVB chains and kernel modules before attempting packaging.
4. Do not flash experimental images; no complete ROM compile or boot has been validated.

**Scope:** this report is derived from GitHub Actions logs and its checksum-validated metadata artifact, not an independent `lpdump` result.
