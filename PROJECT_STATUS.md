# MIST / LINEAGEOS 23.2 — LIVE PROJECT STATUS AND NEXT-CHAT HANDOVER

**Last reviewed: 12 November 2026 (Malaysia time).**  
**Start every new chat here:** `copilot_project/PROJECT_STATUS.md`. Check GitHub Actions for later runs and update this file with **verified** changes before ending a development session. This is a living Markdown status file. For an explicit **HANDOVER**, also generate a proper, updated PDF; do not merely reuse an older PDF.

## 1. Goal and strict rules

Bring up Android 16 **LineageOS 23.2** for **Redmi Note 17 5G / mist**, platform `parrot` / Qualcomm SM4450, based on stock Xiaomi Global **OS3.0.304.0.WPUMIXM**. Firmware MD5 `c4450c4e168052ca9de1211306d3beff`.

- **ONLY existing `main` branches. NO pull requests, NO new branches.**
- All GitHub Actions workflows, experiments, research scripts, temporary tools, and downloaded or staged archives must live **only** in `nobodyAtall-code/copilot_project`.
- Production device, vendor and kernel trees receive **only device-specific, evidence-reviewed source and necessary files**; never put Actions or experimental scripts in them.
- The `sm4450-development` GitHub organization is **architectural reference only**. Never blindly copy another device's partitions, DTBO, SELinux, proprietary blobs or device settings.
- `GH_PAT` exists as a secret in `copilot_project`. Never disclose it, paste it in code or logs, or assume publish permissions before verification. The research-only workflows use the GitHub Actions token.
- Never publish `persist`, `modemst`, individual phone calibration, private identifiers, signing keys or other sensitive partitions. No stock bloat wholesale.
- Do not wipe or replace the user's existing local LineageOS checkout until read-only inventory and backup.
- A successful *research job* is **not** a successful Lineage build or device boot.

## 2. Repository ownership and current role

| Repository | Role | Current state |
| --- | --- | --- |
| [copilot_project](https://github.com/nobodyAtall-code/copilot_project) | research, staging, workflows, persistent reports and these handover notes | active, `main` |
| [android_device_xiaomi_mist](https://github.com/nobodyAtall-code/android_device_xiaomi_mist) | production device configuration | preliminary six-file skeleton only; not build-ready |
| [proprietary_vendor_xiaomi_mist](https://github.com/nobodyAtall-code/proprietary_vendor_xiaomi_mist) | production proprietary vendor tree | still empty |
| [android_device_xiaomi_mist-kernel](https://github.com/nobodyAtall-code/android_device_xiaomi_mist-kernel) | stock-compatible kernel prebuilts/integration | still empty |
| [android_kernel_xiaomi_mist](https://github.com/nobodyAtall-code/android_kernel_xiaomi_mist) | Linux 6.6.118 source | populated; includes `mist.bzl` and `build.config.msm.mist` |

Existing device skeleton: `BoardConfig.mk`, `AndroidProducts.mk`, `device.mk`, `lineage_mist.mk`, `extract-files.py`, `setup-makefiles.py`. Preserve these; extend only with verified configuration.

## 3. Completed and verified pipeline

| Run | Status | What it established |
| --- | --- | --- |
| [43174896778](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43174896778) | success | source firmware archive staged, boot images staged, EROFS partitions inventoried |
| [43178657329](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43178657329) | success | vendor source SHA256 and seven boot image hashes passed; 4,373 vendor archive entries inventoried |
| [43181251762](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43181251762) | success | 107 VINTF XML, 132 HAL names, 3 fstab files, 47 mountpoints, 143 RC files, 251 services, 14 module metadata files |
| [43183815801](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43183815801) | success | archive membership cross-check: 4,352 safe paths; 180/198 service references found; three modules.load lists matched by basename |
| [43184532913](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43184532913) | success | publishes durable membership Markdown/JSON reports in `research/generated/` |
| [43185479167](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43185479167) | **VERIFY status** | newly added missing service/KeyMint near-match reconciliation; status was in progress when this note was authored |

**Previous failure context**: early stock configuration review runs failed on Python invalid Markdown backtick escapes. Fixed and verified by successful run 43181251762. The first archive membership run failed before later runs succeeded.

### Important source data

- Stock firmware Android 16, build `OS3.0.304.0.WPUMIXM`; `mist`, `mist_global`, SM4450.
- Stock kernel `6.6.118-android15-8-g666ad52b8230-ab15657065-4k`; physical `super` size from fastboot is 10,200,547,328 bytes, **not** necessarily the dynamic group usable size.
- Eight populated dynamic images: `system_a`, `system_ext_a`, `product_a`, `vendor_a`, `vendor_dlkm_a`, `system_dlkm_a`, `odm_a`, `mi_ext_a`.
- Stock filesystem `/data`: F2FS with wrapped-key metadata encryption; stock `/vendor`: EROFS. The fstab carries both EROFS and EXT4 alternatives, AVB chaining and HyperOS overlays. **Do not copy overlays blindly.**
- Verified stock boot chain: `boot.img`, `init_boot.img`, `vendor_boot.img`, `recovery.img`, `dtbo.img`, `vbmeta.img`, `vbmeta_system.img`.
- Stock artifact archives and review artifacts from 12 November expire **26 November 2026** unless separately preserved or regenerated.

### Membership evidence (not blob approval)

From the published `mist-archive-membership.json`:
- 4,373 tar archive members; 4,352 allowed names; 21 rejected paths by safety filter.
- 198 init executable declarations under vendor/ODM; **180 present, 18 absent references**, with some duplicate executable paths.
- 105 stock VINTF documents with HAL declarations: **104 file paths present, 1 absent**. The absent path is `vendor_a/etc/vintf/manifest/android.hardware.security.keymint-service-qti.xml`; it declares KeyMint, SecureClock, SharedSecret in the original parsed config. This does **not** establish that these HALs are absent from runtime.
- The 18 missing service references include `/vendor/bin/hw/rild`, `/vendor/bin/ATFWD-daemon`, `/vendor/bin/wifi_qos_daemon`, plus legacy/factory/optional candidates. Do **not** add broken binaries or delete init services based only on the name inventory.
- `modules.load` checks: system_dlkm flattened 78, system_dlkm versioned 78, vendor_dlkm 350; **zero missing .ko basenames** in archive inventory. Note 350 vendor load entries but 268 distinct `modules.dep` records. Basename-only matches prove neither module ABI nor load compatibility.

## 4. Research/report files — read in this order

1. `research/device-facts.md`: on-device facts and boot/partition sizes.
2. `research/mist-evidence-reconciliation-2026-11-12.md`: HAL/RC evidence and key cautions.
3. `research/generated/mist-stock-config.md` and `.json`: actual VINTF, init, fstab and module research output.
4. `research/generated/mist-archive-membership.md` and `.json`: service and manifest path membership results.
5. `research/generated/mist-missing-path-review.md` and `.json` **once run 43185479167 succeeds**: alternative paths and KeyMint-related filename candidates; candidates are **never proof of equivalence**.
6. `research/stock-audit-run-43174896778.md` and `research/staged-archive-audit-run-43178657329.md`: raw extraction and hash evidence.
7. `research/handover/Mist_LineageOS_23_2_Handover_2026-11-12_v2.pdf`: previous dated PDF handover; superseded by this live status file for new work.

## 5. Next actionable development tasks (in priority order)

1. **START WITH LATEST RUN**: check status and logs for [43185479167](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43185479167). If failure, fix the underlying script/workflow on `copilot_project/main`; if successful, inspect `mist-missing-path-review.md/json` and report the precise alternate filenames/KeyMint evidence. Update this status file.
2. Resolve missing KeyMint VINTF path and missing service executables **against real stock archive members**, relevant symlink targets, executable presence, filename variations, alternate partition mounts and active SKU manifest combinations. Distinguish missing vs optional factory features. Do not invent results.
3. Build a safe, read-only **file metadata and recursive ELF DT_NEEDED** checker for a *curated candidate set*: preserve provenance, hash, type, symlinks, permissions, dependency edges, missing library resolution and partition-mount mapping. Keep the analysis workflow solely inside `copilot_project`.
4. Inspect actual boot/vendor_boot/init_boot/recovery images and DTBO, ramdisk fragments, module lists/load ordering and AVB flags against the mist kernel tree. Populate kernel prebuilts only when proven correct.
5. Obtain authoritative full `lpdump` group capacity metadata. Do not infer dynamic group size from extracted image sizes or `SUPER_IMAGE_SIZE` kernel build variable.
6. Create a **reviewed, concise proprietary-files.txt** tied to stock paths, plus standard extract-utils makefiles. For large binary publishing, put publishing logic in `copilot_project` only, validate scoped `GH_PAT` permissions, and apply a strict verified file allowlist.
7. Complete production device tree BoardConfig, init, device.mk, VINTF, overlays, F2FS encryption, AVB, dynamic partitions, recovery and SEPolicy based on exact mist facts.
8. Inventory/back up existing local LineageOS 23.2 checkout, then attempt first `lunch lineage_mist-userdebug` and full build; debug compile, VINTF, SELinux and boot separately. No functionality is yet validated.

## 6. What has NOT been completed (do not overclaim)

- No final or approved `proprietary-files.txt`.
- No populated production proprietary vendor or kernel-prebuilt repository.
- No verified complete DT_NEEDED library closure, symlink/mode metadata, or actual module ABI assessment.
- No validated dynamic partition group capacities or finished BoardConfig/AVB/SELinux configuration.
- No ROM build, lunch verification, boot, recovery validation or hardware testing.
- No evidence that missing service names mean their functionality is absent from the device.

## 7. How to proceed in the next ChatGPT chat

**Copyable continuation instruction:**

> Continue my Redmi Note 17 5G (mist) LineageOS 23.2 Android 16 bring-up. Read `nobodyAtall-code/copilot_project/PROJECT_STATUS.md` on GitHub main first, then check the latest Actions run and report any new results. Keep this status document updated after substantive work. Next inspect missing stock service paths and KeyMint references from the new research report, and implement only evidence-based vendor/kernel bring-up. Commit only to existing main branches, never use PRs or new branches, and keep ALL workflows and experiments exclusively in `copilot_project`. Other SM4450 device trees are architectural references, not mist configurations. Do not expose GH_PAT or touch local LineageOS checkout destructively. Tell me what was committed, verified, and still pending. When I say HANDOVER, produce a freshly checked, properly formatted PDF in addition to updating this repo status document.

This file is the durable canonical continuation record. **Update it when future results change; do not leave it frozen after the next workflow completes.**
