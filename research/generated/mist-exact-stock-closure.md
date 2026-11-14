# Mist exact stock firmware provenance

Source: SHA256-verified OS3.0.304.0.WPUMIXM stock vendor archive

| Group | Stock path | Present | Bytes | SHA256 prefix |
|---|---|---|---:|---|
| camera_helper | `vendor_a/bin/init.qti.cam.perfopt.sh` | yes | 1145 | afbff16da5cbeaff |
| camera_helper | `vendor_a/etc/init.qti.cam.perfopt.sh` | NO | - | - |
| camera_helper | `odm_a/bin/init.qti.cam.perfopt.sh` | NO | - | - |
| camera_rc | `vendor_a/etc/init/vendor.qti.camera.provider-service_64.rc` | yes | 1207 | da13461fcd56cdb4 |
| camera_vintf | `vendor_a/etc/vintf/manifest/vendor.qti.camera.provider.xml` | yes | 324 | b2ea3cfac60a7174 |
| camera_vintf | `vendor_a/etc/vintf/manifest/vendor.qti.camera.postproc-impl.xml` | yes | 334 | daaaad11889b5f53 |
| keymint_vintf | `vendor_a/etc/vintf/manifest/android.hardware.security.keymint-service-qti.xml` | yes | 810 | 229835b6b669a1c6 |
| keymint_rc | `vendor_a/etc/init/android.hardware.security.keymint-service-qti.rc` | yes | 456 | 4f2aea385713f86a |
| selinux | `vendor_a/etc/selinux/vendor_file_contexts` | yes | 131138 | f42262160ae2d8fa |
| selinux | `vendor_a/etc/selinux/vendor_service_contexts` | yes | 17687 | a75884a7e351223e |
| selinux | `vendor_a/etc/selinux/vendor_hwservice_contexts` | yes | 8306 | e0ac85ebdbb113e9 |
| selinux | `vendor_a/etc/selinux/vendor_sepolicy.cil` | yes | 1403650 | 959ef76be5aa958f |
| selinux | `vendor_a/etc/selinux/precompiled_sepolicy` | NO | - | - |
| selinux | `odm_a/etc/selinux/odm_file_contexts` | yes | 91 | 83cf304165f2f4e7 |
| selinux | `odm_a/etc/selinux/odm_sepolicy.cil` | yes | 93848 | 51fb464b7e6668ab |
| camera_module | `vendor_dlkm_a/lib/modules/camera.ko` | yes | 7150376 | 0ade7e601c4387d1 |
| camera_module | `vendor_dlkm_a/lib/modules/modules.dep` | yes | 37992 | 7ee6bfcbbc45cef3 |
| camera_module | `vendor_dlkm_a/lib/modules/modules.load` | yes | 5733 | 1b41cd3d73bcfbe8 |

## Camera helper and module matches

- `vendor_a/bin/init.qti.cam.perfopt.sh`
- `vendor_dlkm_a/lib/modules/camera.ko`

## Camera RC references

- `exec u:r:vendor_qti_init_shell:s0 -- /vendor/bin/init.qti.cam.perfopt.sh`

**No binary or SELinux policy content has been published.**
No runtime, overlay selection or ABI compatibility is implied.
