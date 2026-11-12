# Mist Android 16 — concrete ELF linkage triage, 13 November 2026

## Verified original run and source

[Unified run 43274659481](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43274659481), job `131379746059`: **SUCCESS** after explicit user-provided review. [Artifact 13970175925](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43274659481/artifacts/13970175925) was downloaded and `reports/mist-elf-dependency-triage.json` plus its Markdown opened and reviewed. The original vendor archive comes from Xiaomi Global `OS3.0.304.0.WPUMIXM` with SHA256 checked against run 43174896778.

The read-only scanner accepted **4,352** paths, parsed **2,110** ELFs, traversed **157** paths, recorded **1,386 total DT_NEEDED edges** and **637 unresolved edges in the bounded stock vendor/ODM archive**. Deduplication yields **11 unique unresolved SONAMEs**, not 637 missing binaries. Current structural preflight errors: `[]`; `ready_for_rom_build_claim=false`. Unified report passed 7/15 *offline* gates.

## The 11 unresolved SONAMEs, with distinct referencing ELF count

| SONAME | Source ELF count | Source classification | First priority |
| --- | ---: | --- | --- |
| `libc.so` | 157 | candidate Android platform | check target Android 16 linker namespace |
| `libdl.so` | 157 | candidate Android platform | check target Android 16 linker namespace |
| `libm.so` | 157 | candidate Android platform | check target Android 16 linker namespace |
| `liblog.so` | 80 | candidate Android platform | check target Android 16 linker namespace |
| `libbinder_ndk.so` | 73 | candidate Android platform | check target Android 16 linker namespace |
| `libvndksupport.so` | 5 | unclassified | platform vendor availability and namespace |
| `libandroid_net.so` | 3 | unclassified | framework/APEX vendor availability and namespace |
| `android.hardware.security.keymint-V3-ndk.so` | 2 | unclassified | **KeyMint priority** |
| `android.hardware.keymaster@4.0.so` | 1 | unclassified | **KeyMint/Keymaster priority** |
| `android.hardware.keymaster@4.1.so` | 1 | unclassified | **KeyMint/Keymaster priority** |
| `libapexsupport.so` | 1 | unclassified | platform/APEX vendor namespace |

Relevant **stock archive origin ELFs**:
- `android.hardware.security.keymint-V3-ndk.so` was needed by `vendor_a/lib64/libqtikeymint.so` and `vendor_a/lib64/libspukeymint.so`.
- `android.hardware.keymaster@4.0.so` and `android.hardware.keymaster@4.1.so` by `vendor_a/lib64/libqtikeymint.so`.
- `libvndksupport.so` by `vendor_a/lib64/libbinder.so`, `libhardware.so`, `libhidlbase.so`, `libqcrilNr.so` and `libutils.so`.
- `libandroid_net.so` by `vendor_a/lib64/lib-imscommon.so`, `lib-imsdpl.so` and `libcneapiclient.so`.
- `libapexsupport.so` has one origin; see exact `sample_origins` in original artifact.

## Engineering decisions and safeguards

1. Do **not** copy host-system, system/APEX or another device's libraries to vendor merely because their names are unresolved in this partition-scoped scanner.
2. Verify actual LineageOS 23.2 `vendor_available`/stub/NDK declarations, linker namespace rules and Android 16 VNDK model for these 11 libraries. The on-disk AOSP modules and binary ABI matter; filename agreement alone is not enough.
3. Treat the existing **missing exact KeyMint VINTF XML archive path** separately from whether the implementation is active, and correlate stock service registration, RC, and related libs. Do not fabricate service executables or VINTF fragments.
4. Inspect 31 existing production Soong modules against platform modules and build rules, then attempt a real `lunch`/Soong compilation; structural preflight does not demonstrate compilation.
5. No change to production BoardConfig dynamic group maxima or AVB signing until official AOSP/liblp and OTA/snapshot evidence. Physical boot testing remains necessary.

This is a bounded stock ELF analysis, not proof of complete runtime `DT_NEEDED` closure, ABI/SONAME availability across system/APEX, AVB, SELinux or device functionality.
