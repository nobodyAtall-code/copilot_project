# MIST / LINEAGEOS 23.2 — PROJECT HANDOVER
Technical continuation and development roadmap | 12 November 2026 (Malaysia)
Device: Redmi Note 17 5G (mist) | SoC: Qualcomm SM4450 (parrot)
Latest checked GitHub Actions: run 43181251762 — SUCCESS

## 1. EXECUTIVE SUMMARY
The project is creating an original, evidence-based LineageOS 23.2 (Android 16) bring-up for Redmi Note 17 5G (mist). Do NOT treat sm4450-development as a ready-made mist tree. Its repositories are architectural examples only. There is not yet a production proprietary vendor tree or kernel-prebuilt tree and there has been no successful LineageOS build or flash.

The stock Global firmware acquisition, super-partition unpacking, library inventory, source/boot staging, integrity validation, and VINTF/fstab/init/module metadata research pipelines have now passed. The latest stock-configuration review also successfully committed the generated Markdown and JSON research reports to copilot_project/main. The NEXT CHAT MUST begin by examining these stock-specific reports and use them to produce a tightly curated proprietary manifest, then complete vendor/kernel/device configurations.

## 2. LATEST VERIFIED GITHUB ACTIONS — START HERE
Latest run: https://github.com/nobodyAtall-code/copilot_project/actions/runs/43181251762
Job: https://github.com/nobodyAtall-code/copilot_project/actions/runs/43181251762/job/131057511992
Workflow: .github/workflows/stock-config-review.yml
Run head: 71c539c81e238180c514ad9cd386652221c3a48d
Created: 2026-11-12 08:14:00 UTC; result: COMPLETED / SUCCESS.
Verified job steps: checkout main, download audited stock configuration, parse VINTF/fstab/init/module metadata, upload report, and commit report to main all passed.
Generated research: 132 distinct stock-declared HAL names, 107 parsed VINTF XML documents, 3 fstab files and 47 mountpoints, 143 init .rc files and 251 service names, 14 kernel module metadata files, 0 skipped config entries.
Artifact: mist-stock-config-review, ID 13926466670, ZIP size 45,090 bytes; expiry 2026-11-26 08:14 UTC.
Run auto-published two files to copilot_project/main at commit 9d1d923fa45817c2a7a8571155f5537ea78d2c1f:
* https://github.com/nobodyAtall-code/copilot_project/blob/main/research/generated/mist-stock-config.md
* https://github.com/nobodyAtall-code/copilot_project/blob/main/research/generated/mist-stock-config.json
This is a stock CONFIGURATION INVENTORY, NOT proof that every HAL is compatible with LineageOS.

Recent failures were caused by invalid Python backtick escapes in the research script, not damaged firmware:
* run 43179826520 failed at line 144;
* run 43181049262 failed at line 181;
* fixed in main commits 00a7059 and 71c539c; the latest run 43181251762 verifies the second fix worked.
Node.js deprecation warnings from third-party Actions are non-blocking.

## 3. PRIOR VERIFIED WORK
Firmware source: official Global fastboot ROM OS3.0.304.0.WPUMIXM (Android 16), package MD5 c4450c4e168052ca9de1211306d3beff.
Baseline kernel source: Linux 6.6.118, with build.config.msm.mist, mist.bzl and mist-specific module lists available.
Acquisition/extraction run 43172012149 passed and inventoried 11,313 files, 3,030 .so libraries/symlinks across eight populated EROFS logical images.
Full staging run 43174896778 passed, uploaded research 13923423842, all-so 13923129711, vendor-source 13923059799 and boot-images 13924356647. All these artifacts expire 2026-11-26.
Staged archive audit run 43178657329 passed: vendor archive SHA256 and all seven boot-chain image checksums verified; inventoried 4,373 archive entries and 7 boot images. Audit artifact ID 13924823795.
Research candidate staging listed 3,539 vendor/ODM REVIEW CANDIDATES and 42 exclusions; this is NOT an approved proprietary-files.txt. Some excluded vendor apps may contain useful services; inspect case-by-case.

Extracted populated images: system_a, system_ext_a, product_a, vendor_a, vendor_dlkm_a, system_dlkm_a, odm_a and mi_ext_a. Logical image file sizes are NOT dynamic partition group size limits.
Stock boot images staged and hash-checked: boot.img, init_boot.img, vendor_boot.img, dtbo.img, recovery.img, vbmeta.img, vbmeta_system.img.
Stock device facts: boot header v4; dedicated boot/init_boot/vendor_boot/recovery partitions; F2FS /data; dynamic super, A/B and Virtual A/B.
Source research summary: https://github.com/nobodyAtall-code/copilot_project/blob/main/research/stock-audit-run-43174896778.md
Archive audit summary: https://github.com/nobodyAtall-code/copilot_project/blob/main/research/staged-archive-audit-run-43178657329.md

## 4. STOCK CONFIGURATION DISCOVERIES AND CAUTIONS
Research report exposes stock declarations for audio, Bluetooth, camera, display, fingerprint, face, GNSS, graphics, NFC, radio/IMS, sensors, Wi-Fi, power, security and Xiaomi/QTI extension services. Declaration does not show LineageOS compatibility or a functional tested HAL.
Stock fstab.default has both EROFS and ext4 entries for system/product/vendor/system_ext/odm/*dlkm, plus HyperOS overlay mounts. Do NOT blindly copy overlay/product modifications.
Key examples from stock fstab.default: system/system_ext/product use vbmeta_system; vendor/vendor_dlkm/system_dlkm/odm use vbmeta; /data is f2fs with file encryption plus /metadata/vold/metadata_encryption; stock /mnt/vendor/persist must never be embedded as private content.
Fstab source locations: vendor_a/etc/fstab.default, vendor_a/etc/fstab.emmc, vendor_a/etc/charger_fw_fstab.qti. Need review full source before generating LineageOS-specific ramdisk/fstab.
Kernel stock release observed in system_dlkm module paths: 6.6.118-android15-8-g666ad52b8230-ab15657065-4k; check modules against kernel build and vendor_boot.
The current super-metadata research does NOT provide authoritative dynamic partition group capacities. Obtain full lpdump (or equivalent verified stock group metadata) before filling BOARD_SUPER_PARTITION_SIZE and group size assignments.
Do not assume custom ROM must carry every stock service, vendor APK, or SELinux policy.

## 5. REPOSITORIES AND LIVE STATUS
Research/automation: https://github.com/nobodyAtall-code/copilot_project
Latest verified main commit after successful auto-report: 9d1d923fa45817c2a7a8571155f5537ea78d2c1f.
Device tree: https://github.com/nobodyAtall-code/android_device_xiaomi_mist
main SHA be0c8b740d8fed1200b4109f13d7c0d208714449; six preliminary files: AndroidProducts.mk, BoardConfig.mk, device.mk, lineage_mist.mk, extract-files.py, setup-makefiles.py. Still NOT build-ready.
Vendor tree: https://github.com/nobodyAtall-code/proprietary_vendor_xiaomi_mist
Empty repository, no populated main tree.
Kernel prebuilt tree: https://github.com/nobodyAtall-code/android_device_xiaomi_mist-kernel
Empty repository, no populated main tree.
Kernel source: https://github.com/nobodyAtall-code/android_kernel_xiaomi_mist
Populated Linux 6.6.118 source; main SHA fe8024a4c5eea6cf1135e615d44e7a3fb15fedac at last inspection.
Reference organization: https://github.com/sm4450-development — examples ONLY, never bulk copy.

## 6. NON-NEGOTIABLE REPOSITORY AND SECURITY RULES
1. Direct commits ONLY to existing main branches; no new branches or pull requests.
2. ALL workflows, research scripts, staging archives and experiments belong exclusively in copilot_project; no workflows or disposable research scripts in the production device, vendor or kernel trees.
3. Only reviewed device-specific source, makefiles and required proprietary blobs belong in production repos; no blind copying of another model's sky configuration or Xiaomi HyperOS bloat.
4. GH_PAT exists as an Actions secret in copilot_project; NEVER print or request its value. It has not been validated for production binary publishing. Research workflow uses GITHUB_TOKEN for its own repo.
5. Never commit persist/modemst, phone-specific calibration, keys, credentials, device identifiers or secrets. Preserve symlinks, executable modes and ELF dependencies when publishing approved blobs.
6. Local LineageOS 23.2 checkout may contain old modifications; inventory and back up before removing anything. Never run destructive cleanup blindly.
7. Do NOT say device files are bootable, SELinux passes, hardware works or flashing is safe until validated.
8. 'handover' means create an up-to-date, proper PDF: check live GitHub status, summarize verified work, failures, exact next actions, constraints and links; supply a downloadable PDF.

## 7. NEXT CHAT — PRIORITIZED WORK PLAN
STEP 1 — READ BOTH GENERATED RESEARCH REPORTS: research/generated/mist-stock-config.md and .json on copilot_project/main. Inspect actual VINTF HAL definitions (versions/instances), fstab full mount flags, RC service executable paths and module load/dependency lists. Do not just use summary counts.
STEP 2 — COMPARE WITH STOCK ARCHIVES: inspect source archive and verified boot images. Work out which stock HAL binaries, .so dependencies, firmware, configs, XML, init RC and permission files are required; distinguish stock-only services and potential telephony/IMS dependencies. Produce reviewable curated proprietary-files.txt, no bulk import.
STEP 3 — BOOT/KERNEL INTEGRATION: unpack boot, init_boot, vendor_boot, dtbo, recovery; identify header, DTB/DTBO, ramdisk fragments and ordered module load lists. Compare with kernel 6.6.118 source, mist.bzl and modules.list.msm.mist. Populate kernel-prebuilt repo only with verified stock-compatible required inputs.
STEP 4 — COMPLETE DEVICE TREE: use mist-specific fstab, init and overlays; verify VINTF, boot image geometry, AVB chaining, F2FS encryption, OTA partitions, dynamic group sizes, product packages and sepolicy. Update existing device main directly.
STEP 5 — BUILD VENDOR TREE: generate extract-utils standard makefiles and Android.bp/BoardConfigVendor.mk from approved manifest, include blob sha checks and path preservation. For large approved binary pushes, write the publishing workflow exclusively in copilot_project using GH_PAT with least-privilege allowlists, and verify permissions without exposing the token.
STEP 6 — SAFE SOURCE CHECKOUT CLEANUP: request read-only list of old local LineageOS changes and back them up before any targeted removal. Then run lunch lineage_mist-userdebug, build, diagnose, and only later boot test with logs.

## 8. CURRENT PROJECT ACCEPTANCE GATES
DONE: official firmware MD5 gate, EROFS extraction, global inventories, staged source and boot archive checksums, stock configuration audit and generated reports committed.
PENDING: authoritative super group capacities, source archive content dependency review, production proprietary manifest and blobs, kernel-prebuilt inputs, complete device tree, build/lunch, SELinux/VINTF integration, successful ROM build, boot and hardware validation.
Key current risk: temporary GitHub artifacts expire 26 November 2026; research reports are committed and persistent, but large original source/boot archives need retention or reproducible extraction.

## 9. CONTINUATION PROMPT — COPY INTO NEXT CHAT
Continue my Redmi Note 17 5G (mist) LineageOS 23.2 bring-up from this handover PDF. Use the connected GitHub plugin. FIRST confirm the successful run 43181251762 and inspect the auto-generated copilot_project/main files research/generated/mist-stock-config.md and .json at commit 9d1d923. Start implementing the remaining evidence-based vendor and kernel-prebuilt bring-up, with focused review of actual VINTF, fstab, init and module metadata. Keep every repository on main only, never create PRs or branches, and keep workflows/research exclusively in copilot_project. The sm4450-development organization is an architectural reference, not a mist tree. Never copy all its files or stock HyperOS bloat; never expose GH_PAT. Do not disturb the existing local LineageOS checkout until it is inventoried. Report exactly what you commit, what's unverified and next tasks. When I say HANDOVER again, generate a current properly formatted PDF with verified GitHub state and a continuation prompt.

END OF HANDOVER — 12 NOVEMBER 2026
