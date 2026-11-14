# Mist Global firmware — complete source inventory findings (2026-11-14)

## Evidence and scope

- Original Xiaomi Global fastboot ROM: `OS3.0.304.0.WPUMIXM`, original archive MD5 `c4450c4e168052ca9de1211306d3beff`.
- [Full research workflow run 43579076486](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43579076486/job/132399705358) **SUCCESS**, every analysis step passed.
- [Original 22-report archive (artifact 14107138565)](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43579076486/artifacts/14107138565) includes complete extracted research JSON (not raw firmware); local analysis of the actual ZIP was performed before compiling this report. This Markdown is an interpreted summary, not a replacement for JSON evidence.
- This run **does not establish** a flashable ROM, full VINTF compatibility, ABI/signature validity, policy compile or device boot.

## Exact original stock super partition layout

Physical super size observed previously: **10,200,547,328 bytes**. Python verified liblp geometry and all **3** primary/backup metadata slot pairs, and independent pinned Go verified **all nonzero partition sizes and both group descriptors**.

| Group | Maximum bytes | Allocated bytes | Members |
|---|---:|---:|---|
| `qti_dynamic_partitions_a` | 10,190,061,568 | 6,533,066,752 | 8 populated slot-A partitions |
| `qti_dynamic_partitions_b` | 10,190,061,568 | 0 | 8 unallocated slot-B entries |
| `default` | 0 | 0 | none |

**Do not** add group A and group B maxima as simultaneously allocated bytes; they are separate per-slot limits.

| Partition | Verified logical size (bytes) | FS |
|---|---:|---|
| `mi_ext_a` | 1,108,955,136 | EROFS |
| `odm_a` | 17,195,008 | EROFS |
| `product_a` | 3,339,325,440 | EROFS |
| `system_a` | 719,495,168 | EROFS |
| `system_dlkm_a` | 15,286,272 | EROFS |
| `system_ext_a` | 637,571,072 | EROFS |
| `vendor_a` | 669,220,864 | EROFS |
| `vendor_dlkm_a` | 26,017,792 | EROFS |

All eight partition images were extracted and mounted read-only; none was skipped due to unrecognized filesystem type. Per-slot OTA composition, `mi_ext` treatment and full Lineage partition-generation settings still need a purposeful engineering integration review.

## Whole-partition content audit

- **11,313** paths indexed by the existing inventory (includes shared-library symlinks).
- **3,911** parsed ELF records; **3,030** shared-library files/symlinks indexed by pre-existing inventory.
- **460** `.ko` modules in mounted partitions: **268 vendor_dlkm**, **192 system_dlkm**.
- **136** VINTF XML files, **269** init RC files; **15** physical `.img` records.
- **19** unique names unresolved by naive across-partition ELF filename/SONAME lookup (do not call them 19 missing vendor libraries). Examples: `libc.so`, `libdl.so`, `libnativehelper.so`, `libstatssocket.so`, `libstatspull.so`, `libandroidicu.so`, `libbinder_ndk.so` and others. Framework/APEX linker namespaces, partitions and symlinks need exact resolution before committing proprietary duplicates.

## Concrete source-kernel/module compatibility warning

The stock partition-module inventory contains **four different vermagic families**, all sharing an AArch64 architecture string, but not an identical full release identifier:

| Module set | Count | Stock `vermagic` prefix |
|---|---:|---|
| system_dlkm | 192 | `6.6.118-android15-8-g666ad52b8230-ab15657065-4k` |
| vendor_dlkm | 208 | `6.6.118-android15-8-maybe-dirty-4k` |
| vendor_dlkm | 53 | `6.6.118-4k-g57a2451a9bcf` |
| vendor_dlkm | 7 | `6.6.98` |

The **seven** `6.6.98` module files are `binder_gki.ko`, `millet_binder.ko`, `millet_core.ko`, `millet_hs.ko`, `millet_oem_cgroup.ko`, `millet_pkg.ko`, `millet_sig.ko`. Their presence is verified; their **load status and compatibility are not verified**. Do not assume all 460 load, or automatically rebuild/mix them into the source kernel.

The stock `vendor_dlkm_a/lib/modules/camera.ko` reports `6.6.118-4k-g57a2451a9bcf SMP preempt mod_unload modversions aarch64`, with dependencies including `mem_buf_dev`, `clk-qcom`, `qcom_va_minidump`, `qcom-scm`, `qcom_iommu_util`, `socinfo`, `mdt_loader`, `hardware_info`, `qcom-spmi-wled` and `leds-qpnp-flash-v2`. Confirm relevant load order, required symbols, CRC and device sensor DTBO before replacing the stock boot baseline.

## Stock boot chain and first-stage environment

Boot image SHA-256 verification and structural parsing pass. The inventory confirms **22 DTBO entries**, **11 vendor_boot DTBs**, **31 vbmeta descriptors** and **12 vbmeta_system descriptors**. This is *structural* evidence, **not** AVB cryptographic verification or DTBO-to-board selection.

- The stock vendor_boot audit produced **302** CPIO members in one vendor fragment and **17** in init_boot.
- Stock first-stage ramdisk contains `first_stage_ramdisk/fstab.default` and `first_stage_ramdisk/fstab.emmc`.
- Production device `fstab.mist` remains **staged but not installed**. Keep original stock vendor_boot/DTBO/kernel fallback until first-stage init, kernel module compatibility and AVB are validated.

## SELinux — verified source mappings, not build policy

Original vendor/ODM compiled CIL and vendor contexts were confirmed present. Verified stock context regex matches and corresponding stock + curated vendor executable paths exist for all five services:

| Stock executable | Original file-context type |
|---|---|
| Camera perfopt | `vendor_qti_init_shell_exec` |
| Camera provider service | `hal_camera_default_exec` |
| KeyMint QTI service | `vendor_hal_keymint_qti_exec` |
| `qseecomd` | `tee_exec` |
| QSEECom 1.0 HAL | `vendor_hal_qseecom_default_exec` |

The prior stock KeyMint VINTF/RC **exact SHA256** comparison remains verified. No stock CIL was copied into the production source tree. Need to cross-check Lineage/QCOM-owned type definitions, policy file contexts and neverallow compilation before device-specific policy additions.

## Next engineering work (not another redundant full download)

1. Resolve production partition group/image/OTA settings against the independently verified source metadata, particularly `mi_ext`/virtual A/B treatment.
2. Reconcile the four module ABI families, especially seven `6.6.98` files, and preserve stock module collections and load order unless proven compatible.
3. Reconcile platform/APEX-linked SONAMEs before curating more vendor prebuilts; avoid duplicate platform-owned HALs.
4. Integrate SELinux source by checking defined types/contexts in the **actual Lineage + Qualcomm source**, not by pasting compiled stock CIL.
5. Validate source package closure, installed output, `checkvintf` and policy compiler/neverallow **before** full ROM build or flashing.

Generated by evidence review of the completed 22-file original research artifact. No firmware images or proprietary contents published in this report.
