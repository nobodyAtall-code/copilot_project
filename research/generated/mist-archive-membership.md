# Mist stock archive membership gate

**Evidence only; no proprietary manifest is approved by this check.**

- Raw archive members: 4373; prior audit: 4373
- Safe archive member paths: 4352
- Rejected/unsafe member names: 21
- Vendor/ODM init service references: 198
- Present executable paths: 180
- Missing executable paths: 18
- VINTF documents with HAL declarations: 105
- Present such VINTF paths: 104

## Missing referenced executables (requires case-by-case review)
- `/vendor/bin/boringssl_self_test32` referenced by `vendor_a/etc/init/boringssl_self_test.rc`
- `/vendor/bin/check_keymaster` referenced by `vendor_a/etc/init/factorybsp_service.rc`
- `/vendor/bin/check_keybox` referenced by `vendor_a/etc/init/factorybsp_service.rc`
- `/vendor/bin/mmid` referenced by `vendor_a/etc/init/hw/init.qcom.factory.rc`
- `/vendor/bin/wigignpt` referenced by `vendor_a/etc/init/hw/init.qcom.rc`
- `/vendor/bin/sensingdaemon` referenced by `vendor_a/etc/init/hw/init.qcom.rc`
- `/vendor/bin/qvop-daemon` referenced by `vendor_a/etc/init/hw/init.qcom.rc`
- `/vendor/bin/ATFWD-daemon` referenced by `vendor_a/etc/init/hw/init.qcom.rc`
- `/vendor/bin/hw/rild` referenced by `vendor_a/etc/init/hw/init.qcom.rc`
- `/vendor/bin/hw/rild` referenced by `vendor_a/etc/init/hw/init.qcom.rc`
- `/vendor/bin/vm_bms` referenced by `vendor_a/etc/init/hw/init.qcom.rc`
- `/vendor/bin/LKCore` referenced by `vendor_a/etc/init/hw/init.qcom.rc`
- `/vendor/bin/LKCore` referenced by `vendor_a/etc/init/hw/init.qcom.rc`
- `/vendor/bin/hbtp_daemon` referenced by `vendor_a/etc/init/hw/init.qcom.rc`
- `/vendor/bin/chre` referenced by `vendor_a/etc/init/hw/init.qcom.rc`
- `/vendor/bin/check_fatal_err.sh` referenced by `vendor_a/etc/init/hw/init.target.rc`
- `/vendor/bin/init.qti.fm.sh` referenced by `vendor_a/etc/init/init.qti.fm.rc`
- `/vendor/bin/wifi_qos_daemon` referenced by `vendor_a/etc/init/init.vendor.wlan.rc`

## Module load membership (basename only; NOT ABI validation)
- `system_dlkm_a/flatten/lib/modules/modules.load`: 78 load lines; 0 absent .ko basenames; metadata truncated=False
- `system_dlkm_a/lib/modules/6.6.118-android15-8-g666ad52b8230-ab15657065-4k/modules.load`: 78 load lines; 0 absent .ko basenames; metadata truncated=False
- `vendor_dlkm_a/lib/modules/modules.load`: 350 load lines; 0 absent .ko basenames; metadata truncated=False

## Required follow-up gates
- Review archive file types, symlink targets, permissions and SHA256.
- Trace each candidate binary and recursive ELF DT_NEEDED library closure.
- Validate VINTF instance selection, SELinux, init and vendor/ODM paths.
- Inspect boot/vendor_boot ramdisks, exact kernel release and module ABI.
- Obtain authoritative lpdump group sizes before BoardConfig changes.
- Publish only a manually approved curated manifest, never this inventory.
