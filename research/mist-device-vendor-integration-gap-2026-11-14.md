# Mist LineageOS 23.2 — actual device/vendor tree completeness assessment (2026-11-14)

## Source inspection
Verified directly against GitHub main tree listings, not inferred from HAL compilation results:

- `nobodyAtall-code/android_device_xiaomi_mist` — 24 entries / 16 files in recursive listing. Device tree provides `BoardConfig.mk`, `device.mk`, `lineage_mist.mk`, extract/proprietary manifest files, a stock boot snapshot (fstab and `modules.load` text), root fstab, and research docs. **No device-specific SELinux policy files, recovery integration files, or broad hardware configuration trees shown in current main**.
- `nobodyAtall-code/proprietary_vendor_xiaomi_mist` — 77 entries / 73 files in recursive listing, mostly curated service binaries, libraries, matching stock init RC and VINTF XML plus `Android.bp`/`mist-vendor.mk`. This is **not** a full extraction of Xiaomi stock vendor. The repository README says it is incomplete. `mist-vendor.mk` selects curated batches including KeyMint, Bluetooth, GNSS, Power, QSEE, Camera/Lights, Radio; stock Health, Audio, Display, Thermal etc. are intentionally delegated to platform owners to avoid duplicate installs, so simply counting stock source files as installed is invalid.
- `Android.bp` has multiple `check_elf_files: false` declarations. This is a bootstrap bypass, not a passing ELF ABI or linker check.
- `nobodyAtall-code/android_device_xiaomi_mist-kernel` main contains the stock `kernel`, `vendor_boot.img`, `dtbo.img` and SHA256 locks. Local 2026-11-14 07:37 UTC audit confirms stock images now present after checkout sync.

## Proven local results
- HAL batch `mist-hal-all-tests-20261114T072122Z.txt`: 6/6 targeted commands exit 0; Display and Audio/Thermal were incremental no-ops; Camera/Lights stock prebuilts installed.
- Offline readiness `mist-offline-readiness-20261114T073735Z.txt`: 18 PASS / 0 FAIL / 8 WARN / 7 UNVERIFIED. 93 ELF files inspected, 83 *candidate* missing DT_NEEDED names in limited roots; many platform/APEX libs are out of scan scope. 0 device/vendor sepolicy `.te/.cil` and 0 unpacked `.ko` in sampled paths, **not** proof stock vendor_boot lacks modules.

## Unresolved integration gates
1. Device sepolicy and init service context/labels; board security policy paths. Need stock-backed implementation and policy compiler before any production changes.
2. Complete vendor extraction / package parity / exact HAL ownership; compare `proprietary-files.txt`, `Android.bp`, `mist-vendor.mk` with stock inventory. Missing files must be proven from firmware; never fabricate blobs.
3. ELF `DT_NEEDED`, exact SONAME and linker namespace / platform/APEX dependencies, VINTF service registration + framework compatibility. Static XML well-formedness is not `checkvintf`.
4. Vendor_boot embedded modules/DTBs and stock 6.6 kernel ABI; preserve stock boot images while assessing replacement.
5. LP dynamic groups, AVB chain, metadata and full boot/recovery flow; physical super size alone is insufficient.
6. Complete ROM compile/link + real device boot/hardware checks **not yet performed**.

## Next reproducible local audit
User requests one terminal command, one consolidated TXT, no workflows. Published:
`scripts/audit_mist_tree_integration.py` (read-only; repository snapshot, manifest/source/package parity, stage/RC/VINTF, ELF needed names, policy/boot/module inventory). Run on the Linux checkout and submit the resulting `~/mist-tree-integration-<UTC>.txt`. Do not label tree complete on successful execution.

## Repository modification decision
No speculative device/vendor production edits made as part of this inspection. Source-tree completion requires evidence, reviewed stock files and actual local build/checkvintf/SELinux results. The coordination audit and documentation were committed to `copilot_project` only.
