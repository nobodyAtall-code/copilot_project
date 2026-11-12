# Redmi Note 17 5G (mist) — LineageOS 23.2 bring-up workspace

This repository is for stock firmware acquisition, research, partition inventories, extraction tooling, logs and intermediate artifacts. Production build files belong in the separate device/vendor/kernel repositories.

## Ground truth

- Device: Redmi Note 17 5G, codename `mist`
- Platform: Qualcomm SM4450, board platform `parrot`
- Stock Global firmware: `OS3.0.304.0.WPUMIXM` (Android 16)
- Expected full fastboot ROM MD5: `c4450c4e168052ca9de1211306d3beff`
- Stock kernel identified: Linux 6.6.118
- Stock partitions include `system`, `system_ext`, `product`, `vendor`, `vendor_dlkm`, `system_dlkm`, `odm`, and `mi_ext`; verify full super metadata before writing BoardConfig.

## Workflow

`.github/workflows/firmware-acquisition.yml` is a **manual** first-stage workflow. It uses aria2 with up to sixteen range connections to Xiaomi's official CDN, verifies the download MD5, extracts the fastboot archive, then uploads checksums and a partition-image inventory. Actual speed is constrained by the CDN and runner.

The workflow **does not yet** unpack `super.img`, mount or decode EROFS/ext4 images, extract every `.so`, or generate vendor makefiles. These steps must be added only after validating the image inventory and required free disk space. It does not flash devices and it does not write to other repositories.

The full ROM and partitions are intentionally not uploaded as GitHub Actions artifacts in this first stage: the archive and expanded images can exceed storage limits. Artifacts here are reports only, with 14-day retention.

## Rules

- Update only `main`; no pull requests or additional branches.
- Keep research scripts, tests and logs in this workspace.
- Do not carry over Xiaomi HyperOS APKs or unrelated proprietary files blindly into the LineageOS vendor tree.
- Validate all stock-derived values before publishing build configuration.
- Never commit personal device identifiers, bootloader tokens, calibration/persist data, modemst, or private keys.

## Next steps

1. Run firmware acquisition from Actions > Mist Global firmware acquisition > Run workflow.
2. Inspect the artifact's `images.tsv` and confirm whether `super.img` is sparse and which additional images are present.
3. Add controlled super unpacking and raw filesystem extraction; create a file inventory with hashes and .so paths.
4. Produce a minimal, reviewed proprietary-files list and device BoardConfig based on verified stock data.
5. Populate the production repos only with necessary build files/blobs and test LineageOS 23.2 in the existing local source checkout.
