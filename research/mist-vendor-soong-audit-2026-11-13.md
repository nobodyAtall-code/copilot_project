# Mist vendor Soong/product structural audit — 2026-11-13

**Validated scope:** only source references and build-definition consistency in the existing public `main` trees. **Not** a Soong compile, ELF link check, VINTF validation, SELinux check, boot test or flash-ready vendor.

- [Research workflow run 43268147144](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43268147144), job `131357175936`: **SUCCESS**, checked full GitHub Actions logs.
- [Research script improvement cf9f8ca](https://github.com/nobodyAtall-code/copilot_project/commit/cf9f8ca80bd2d2b8ae136cd8153727c56f174750) was added **only to** `copilot_project/scripts/check_mist_rom_preflight.py`. The workflow clones the existing device, vendor and kernel `main` trees read-only. No experimental scripts or Actions were placed in production repos.
- Enumerated exactly **31** Soong module declarations in `proprietary_vendor_xiaomi_mist/Android.bp` and **31** `mist_*` `PRODUCT_PACKAGES` references in `mist-vendor.mk`.
- Every parsed module has a source path present in the vendor tree and a destination path consistent with its reviewed stock source path. No duplicate Soong module names or product package names. No missing or dangling packages.
- Pre-existing 31-entry device `proprietary-files.txt` matches all published stock files; no missing paths. Stock kernel prebuilt SHA256 is still `b7826ac3d30f03a73ce3d6994ef92914c214781f408741cda72939511eff51dc`, matching provenance lock.
- The evidence-backed `BOARD_INIT_BOOT_HEADER_VERSION := 4`, `BOARD_MKBOOTIMG_INIT_ARGS` and `BOARD_RAMDISK_USE_LZ4 := true` checks also passed. **The report still marks `ready_for_rom_build_claim=false` and `flashable=false`.**

**Open:** Actual LineageOS 23.2 Soong module compile/ABI and linker namespace checks, missing proprietary service/library closure (especially RIL/IMS, KeyMint, fingerprint, audio, camera), dynamic-group AOSP `lpdump` validation, boot ramdisk/kernel module/DTB/DTBO packaging, AVB, VINTF and SELinux. No unsupported library was auto-published. The inventory and product consistency checks must never be promoted to a ROM-build success claim.
