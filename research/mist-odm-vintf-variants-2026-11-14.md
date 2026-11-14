# Mist VINTF state after synchronized vendor checkout (2026-11-14)

## Verified local source report

The user-uploaded `mist-vintf-offline-report(1).json` reports exactly **9 selected proprietary vendor VINTF manifest fragments**, **12 parsed HAL interface instances**, **zero duplicate selected instances**, and **zero XML parsing errors**.

Selected groups: Bluetooth, Camera Provider, Gatekeeper, GNSS, Lights, Power, RadioConfig, QTI KeyMint/SecureClock/SharedSecret and QSEECom. The radio configuration service is `android.hardware.radio.config.IRadioConfig/default`; this **does not** declare the actual per-SIM radio data/modem/voice instances.

This is source-only validation, **not** complete merged framework/device compatibility, runtime registration, or device boot.

## Six actual stock ODM selector variants

Derived from firmware-backed `research/generated/mist-stock-config.json` `vintf_files` (stock OS3.0.304.0.WPUMIXM):

| Stock ODM manifest | Radio data/voice | NFC | Secure Element |
|---|---|---|---|
| `manifest_hcesim_dsds.xml` | slot1 + slot2 | INfc/default | SIM1 + SIM2 |
| `manifest_hcesim_ssss.xml` | slot1 | INfc/default | SIM1 |
| `manifest_hcesimese_dsds.xml` | slot1 + slot2 | INfc/default | SIM1 + SIM2 + eSE1 |
| `manifest_hcesimese_ssss.xml` | slot1 | INfc/default | SIM1 + eSE1 |
| `manifest_nonfc_dsds.xml` | slot1 + slot2 | none | SIM1 + SIM2 |
| `manifest_nonfc_ssss.xml` | slot1 | none | SIM1 |

All six are present as *alternatives* in the verified stock ODM filesystem. **Do not concatenate or install all six.** Original firmware inventory does not prove the active runtime SKU. Choosing an incorrect variant could declare a nonexistent second SIM or NFC/eSE interface.

The stock vendor `android.hardware.radio.config.xml` is separate from these ODM variants.

## Remaining source integration

1. Obtain the active booted stock device's radio/NFC ODM manifest selector and relevant non-identifying boot properties.
2. Determine actual init/ODM source packaging from stock, including how `manifest_<variant>.xml` becomes the active `/odm/etc/vintf/manifest.xml`.
3. Preserve original stock vendor_boot/AVB until a signed, independently verified modified boot chain can be produced.
4. Only after exact SKU selection, integrate the corresponding ODM VINTF fragment and confirm it does not duplicate platform-owned vendor HAL registrations.

No production tree files, boot images or OTA partitions were changed by this research note.
