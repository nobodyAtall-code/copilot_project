# Stock mist device facts (observed on device)

Source: user-provided adb getprop, uname, df, mount, fstab and fastboot getvar logs. Personal device tokens and identifiers are deliberately excluded.

| Field | Value |
|---|---|
| ro.product.device | mist |
| ro.product.mod_device | mist_global |
| ro.board.platform | parrot |
| ro.soc.model | SM4450 |
| Android API | 36 (Android 16) |
| Build | OS3.0.304.0.WPUMIXM |
| Build fingerprint | Redmi/mist_global/mist:16/BP2A.250605.031.A3/OS3.0.304.0.WPUMIXM:user/release-keys |
| Bootloader unlocked | yes |
| Active slot | _a |
| Kernel | 6.6.118-android15-8-g666ad52b8230-ab15657065-4k |
| Filesystem /data | f2fs |
| Filesystem /vendor | erofs |
| Filesystem /system | erofs |
| Boot image layout | dedicated boot, init_boot, vendor_boot, recovery, dtbo |
| Dynamic partitions (observed) | system, system_ext, product, vendor, vendor_dlkm, system_dlkm, odm, mi_ext |

## Sizes reported by fastboot

| Partition | Bytes |
|---|---:|
| super | 10200547328 |
| boot_a | 100663296 |
| vendor_boot_a | 100663296 |
| init_boot_a | 8388608 |
| dtbo_a | 25165824 |
| recovery_a | 104857600 |
| vbmeta_a | 65536 |
| metadata | 67108864 |

Caution: fastboot's full physical `super` partition size is **not** the same as the usable sum of the dynamic partition group sizes. Obtain the exact metadata from `lpdump` before writing `BOARD_SUPER_PARTITION_GROUPS` and `BOARD_*_DYNAMIC_PARTITIONS_SIZE`.

The stock fstab supplies both erofs and ext4 alternatives for several dynamic partitions, and identifies AVB chains (system through vbmeta_system; vendor/odm through vbmeta), F2FS encryption options, an optional mi_ext mount, and HyperOS overlay mounts. HyperOS overlay configurations must not be copied without review into LineageOS.

## Pending verification
- Exact super metadata, group names and slots.
- Actual kernel module ordering and dependency lists from vendor_boot, vendor_dlkm, system_dlkm.
- DTB/DTBO compatibility, boot image headers and ramdisk formats.
- VINTF HALs, init services, fs_config, SELinux contexts, audio, camera, sensors and display.
- Selection and testing of proprietary blobs required by LineageOS 23.2.
