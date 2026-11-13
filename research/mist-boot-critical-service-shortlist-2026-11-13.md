# Mist boot-critical stock service path review — 13 November 2026

Stock: Xiaomi Global OS3.0.304.0.WPUMIXM. Data: `mist-stock-config.json` and `mist-archive-membership.json` (audited firmware). This is a **publication shortlist**, NOT proof of HAL completeness, safe copy, linker closure or boot. Binary paths and RC entries are grounded in audited stock source.

| Subsystem | Stock RC | Executable | Present in source archive | Next gate |
|---|---|---|---|---|
| KeyMint | `vendor_a/etc/init/android.hardware.security.keymint-service-qti.rc` | `/vendor/bin/hw/android.hardware.security.keymint-service-qti` | NO / unverified | Validate ELF DT_NEEDED, RC and VINTF; publish verified dependencies |
| Radio | `vendor_a/etc/init/qcrilNrd.rc` | `/vendor/bin/hw/qcrilNrd` | Yes | Validate ELF DT_NEEDED, RC and VINTF; publish verified dependencies |
| Audio | `vendor_a/etc/init/audiohalservice_qti.rc` | `/vendor/bin/hw/audiohalservice.qti` | Yes | Validate ELF DT_NEEDED, RC and VINTF; publish verified dependencies |
| Camera | `vendor_a/etc/init/vendor.qti.camera.provider-service_64.rc` | `/vendor/bin/hw/vendor.qti.camera.provider-service_64` | Yes | Validate ELF DT_NEEDED, RC and VINTF; publish verified dependencies |
| Sensors | `vendor_a/etc/init/android.hardware.sensors-service-multihal.rc` | `/vendor/bin/hw/android.hardware.sensors-service.multihal` | Yes | Validate ELF DT_NEEDED, RC and VINTF; publish verified dependencies |
| Power | `vendor_a/etc/init/android.hardware.power-service.rc` | `/vendor/bin/hw/android.hardware.power-service` | Yes | Validate ELF DT_NEEDED, RC and VINTF; publish verified dependencies |
| Fingerprint | `vendor_a/etc/init/fingerprint-odm.rc` | `/vendor/bin/hw/android.hardware.biometrics.fingerprint-service.odm` | Yes | Validate ELF DT_NEEDED, RC and VINTF; publish verified dependencies |
| USB | `vendor_a/etc/init/android.hardware.usb-service.qti.rc` | `/vendor/bin/hw/android.hardware.usb-service.qti` | Yes | Validate ELF DT_NEEDED, RC and VINTF; publish verified dependencies |

Do not create vendor Soong module names or install paths until checking duplicate Lineage implementations and full linker closure. The KeyMint XML missing from the selected stock archive is not evidence the HAL is absent. The stock Health implementation must not be duplicated.
