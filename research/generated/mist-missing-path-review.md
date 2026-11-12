# Mist missing service / KeyMint path review

**Research only. No production blobs approved by filename matching.**

- Source: successful stock archive membership gate run 43184532913
- Archived safe paths: 4352
- Absent init executable references: 18
- Unique absent executable paths: 16
- Missing stock VINTF paths: 1
- Security-related stock filenames: 13

## Missing references and stock-path alternatives

### init_executable: vendor_a/bin/ATFWD-daemon
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/bin/ccid_daemon_nr, vendor_a/bin/cnss-daemon, vendor_a/bin/edgnss-daemon, vendor_a/bin/ftmdaemon, vendor_a/bin/ims_rtp_daemon, vendor_a/bin/imsdaemon, vendor_a/bin/qcom-system-daemon, vendor_a/bin/slim_daemon, vendor_a/bin/time_daemon, vendor_a/bin/wdsdaemon, vendor_a/bin/xtra-daemon

### init_executable: vendor_a/bin/LKCore
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/bin/more

### init_executable: vendor_a/bin/boringssl_self_test32
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/bin/boringssl_self_test64, vendor_a/bin/color_sampling_test, vendor_a/bin/qsh_wifi_test, vendor_a/bin/xiaomi_cellinfo_test

### init_executable: vendor_a/bin/check_fatal_err.sh
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: none

### init_executable: vendor_a/bin/check_keybox
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/bin/StoreKeybox, vendor_a/bin/chcon, vendor_a/bin/checkpoint_gc, vendor_a/bin/spu_install_keybox

### init_executable: vendor_a/bin/check_keymaster
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/bin/chattr, vendor_a/bin/sec_log_enabler

### init_executable: vendor_a/bin/chre
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/bin/chattr, vendor_a/bin/chgrp, vendor_a/bin/chroot, vendor_a/bin/chrt, vendor_a/bin/echo, vendor_a/bin/free, vendor_a/bin/grep, vendor_a/bin/head, vendor_a/bin/more, vendor_a/bin/nice, vendor_a/bin/true, vendor_a/bin/unshare

### init_executable: vendor_a/bin/hbtp_daemon
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/bin/boot_mode, vendor_a/bin/ccid_daemon_nr, vendor_a/bin/cnss-daemon, vendor_a/bin/edgnss-daemon, vendor_a/bin/ftmdaemon, vendor_a/bin/hal_proxy_daemon, vendor_a/bin/ims_rtp_daemon, vendor_a/bin/imsdaemon, vendor_a/bin/slim_daemon, vendor_a/bin/time_daemon, vendor_a/bin/wdsdaemon, vendor_a/bin/xtra-daemon

### init_executable: vendor_a/bin/hw/rild
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/bin/hw/qcrilNrd

### init_executable: vendor_a/bin/init.qti.fm.sh
- Exact path present: False
- Same basename elsewhere: vendor_a/etc/init.qti.fm.sh
- Similar file names in same directory: vendor_a/bin/init.mdm.sh, vendor_a/bin/init.qcom.coex.sh, vendor_a/bin/init.qcom.sdio.sh, vendor_a/bin/init.qcom.sh, vendor_a/bin/init.qcom.usb.sh, vendor_a/bin/init.qcrild.sh, vendor_a/bin/init.qti.cam.perfopt.sh, vendor_a/bin/init.qti.kernel.debug.sh, vendor_a/bin/init.qti.kernel.sh, vendor_a/bin/init.qti.media.sh, vendor_a/bin/init.qti.qcv.sh, vendor_a/bin/init.qti.write.sh

### init_executable: vendor_a/bin/mmid
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/bin/comm, vendor_a/bin/find, vendor_a/bin/id, vendor_a/bin/mlid, vendor_a/bin/qmipriod, vendor_a/bin/rmmod, vendor_a/bin/ssgqmigd

### init_executable: vendor_a/bin/qvop-daemon
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/bin/cnss-daemon, vendor_a/bin/edgnss-daemon, vendor_a/bin/ftmdaemon, vendor_a/bin/hal_proxy_daemon, vendor_a/bin/ims-dataservice-daemon, vendor_a/bin/ims_rtp_daemon, vendor_a/bin/imsdaemon, vendor_a/bin/qcom-system-daemon, vendor_a/bin/slim_daemon, vendor_a/bin/time_daemon, vendor_a/bin/wdsdaemon, vendor_a/bin/xtra-daemon

### init_executable: vendor_a/bin/sensingdaemon
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/bin/ccid_daemon_nr, vendor_a/bin/cnss-daemon, vendor_a/bin/edgnss-daemon, vendor_a/bin/ftmdaemon, vendor_a/bin/ims_rtp_daemon, vendor_a/bin/imsdaemon, vendor_a/bin/qcom-system-daemon, vendor_a/bin/sendevent, vendor_a/bin/setsid, vendor_a/bin/slim_daemon, vendor_a/bin/time_daemon, vendor_a/bin/wdsdaemon

### init_executable: vendor_a/bin/vm_bms
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/bin/devmem, vendor_a/bin/vmmgr, vendor_a/bin/vmstat

### init_executable: vendor_a/bin/wifi_qos_daemon
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/bin/ccid_daemon_nr, vendor_a/bin/cnss-daemon, vendor_a/bin/edgnss-daemon, vendor_a/bin/ftmdaemon, vendor_a/bin/hal_proxy_daemon, vendor_a/bin/ims_rtp_daemon, vendor_a/bin/imsdaemon, vendor_a/bin/qcom-system-daemon, vendor_a/bin/slim_daemon, vendor_a/bin/time_daemon, vendor_a/bin/wdsdaemon, vendor_a/bin/xtra-daemon

### init_executable: vendor_a/bin/wigignpt
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/bin/gzip, vendor_a/bin/xtwifi-client

### vintf_manifest: vendor_a/etc/vintf/manifest/android.hardware.security.keymint-service-qti.xml
- Exact path present: False
- Same basename elsewhere: none
- Similar file names in same directory: vendor_a/etc/vintf/manifest/android.hardware.drm-service.clearkey.xml, vendor_a/etc/vintf/manifest/android.hardware.gnss-aidl-service-qti.xml, vendor_a/etc/vintf/manifest/android.hardware.health-service.qti.xml, vendor_a/etc/vintf/manifest/android.hardware.ir-service.example.xml, vendor_a/etc/vintf/manifest/android.hardware.sensors-multihal.xml, vendor_a/etc/vintf/manifest/android.hardware.thermal-service.qti.xml, vendor_a/etc/vintf/manifest/android.hardware.usb-service.qti.xml, vendor_a/etc/vintf/manifest/android.hardware.usb.gadget-service.qti.xml, vendor_a/etc/vintf/manifest/android.hardware.wifi-service.xml, vendor_a/etc/vintf/manifest/vendor.qti.hardware.qseecom@1.0-service.xml, vendor_a/etc/vintf/manifest/vendor.qti.hardware.servicetrackeraidl-service.xml, vendor_a/etc/vintf/manifest/vendor.qti.hardware.soter-service.xml
- HAL declarations: android.hardware.security.keymint, android.hardware.security.secureclock, android.hardware.security.sharedsecret

## Stock KeyMint / Keymaster-related paths

- vendor_a/lib64/android.hardware.security.secureclock-V1-ndk.so
- vendor_a/lib64/android.hardware.security.sharedsecret-V1-ndk.so
- vendor_a/lib64/android.hardware.security.sharedsecret-V2-ndk.so
- vendor_a/lib64/libkeymaster_messages.so
- vendor_a/lib64/libkeymasterdeviceutils.so
- vendor_a/lib64/libkeymasterprovision.so
- vendor_a/lib64/libkeymasterutils.so
- vendor_a/lib64/libqtikeymaster4.so
- vendor_a/lib64/libqtikeymint.so
- vendor_a/lib64/libspukeymint.so
- vendor_a/lib64/libspukeymintdeviceutils.so
- vendor_a/lib64/libspukeymintprovision.so
- vendor_a/lib64/libspukeymintutils.so

## Interpretation and next checks

- A missing stock RC executable may be an optional upstream placeholder, a different partition path, or an actually absent binary; investigate.
- Stock VINTF declarations can vary by device SKU or init-time manifest fragments. Confirm the active runtime manifest.
- Inspect symlink types/targets, source file modes and sha256, then recursive DT_NEEDED dependency closure before a proprietary manifest.
- Compare the KeyMint executable, its VINTF service registration, security policy and library dependencies. Missing one listed XML path does not prove the KeyMint HAL itself is absent.
- Do not publish all stock binaries or unreviewed Qualcomm/Xiaomi services.

Detailed records: mist-missing-path-review.json
