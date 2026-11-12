# Redmi Note 17 5G (mist) — LineageOS 23.2 bring-up workspace

Temporary research/extraction workspace. Production build files go only into the dedicated device, vendor and kernel repositories after review.

## Device and firmware baseline

- Device: Redmi Note 17 5G (`mist`), Qualcomm SM4450 (`parrot`)
- Stock Android 16 Global ROM: `OS3.0.304.0.WPUMIXM`
- Full fastboot ROM MD5: `c4450c4e168052ca9de1211306d3beff`
- Stock kernel: 6.6.118
- Source of stock-derived fstab, mount and partition observations: `research/device-facts.md`

## Acquisition and partition extraction

Start `.github/workflows/firmware-acquisition.yml` manually on the **main** branch.

1. Run `scripts/multicdn.py`: probe Xiaomi/Aliyun CDN alternatives, download byte ranges with 16 workers, then **verify the complete MD5**.
2. Extract fastboot archive and inventory physical `.img` files. The verified `.tgz` is deleted after extraction to conserve disk.
3. Build a pinned Go super-partition reader (commit is recorded under `reports/lpunpack-version.txt`).
4. Run `scripts/extract_partitions.sh` to convert sparse super images where needed, unpack logical partition images and mount recognized EROFS/ext4 images read-only.
5. Run `scripts/inventory_partitions.py` to inventory files across mounted logical partitions, hash each shared library and create `all-shared-libraries.tar.zst`.
6. Run `scripts/stage_vendor_sources.py` to generate **review-only** `proprietary-candidates.txt`, exclusions and a source archive of `vendor`, `odm`, `vendor_dlkm`, and `system_dlkm` files.
7. Run `scripts/stage_boot_images.sh` to retain boot, init_boot, vendor_boot, dtbo, recovery and vbmeta images (never persist or modemst).

The default run uploads **four artifacts**:
- `mist-global-OS3.0.304.0-research`: all paths, shared library paths/hashes, firmware-image lists, super metadata, mount results, checksums and CDN probe data.
- `mist-global-OS3.0.304.0-all-so`: the compressed library content and symlinks extracted from all successfully mounted logical filesystem images.

- `mist-global-OS3.0.304.0-vendor-source`: stock vendor/odm and kernel-module partition file sources, with source archive checksum.
- `mist-global-OS3.0.304.0-boot-images`: stock boot-chain images and their SHA256 checksums.

An **optional** `upload_raw_partitions` input uploads raw unpacked logical images. Disabled by default due to large GitHub Actions artifact storage consumption; enabling it may exceed repository quotas. Physical firmware partitions such as boot, vendor_boot, dtbo and modem are inventoried by filename and hash, but are not mounted as EROFS/ext4 or decoded as boot/ramdisk containers in this stage.

**Important:** A successful download does not prove this second-stage extractor works. The first run must confirm the super image layout, mount support, storage headroom and complete library archive. Missing, unsupported or failed filesystem extractions must be treated as incomplete, never silently considered fully extracted.

## Repository rules

- `main` only; no PRs or new branches.
- All research scripts, test tooling and intermediate outputs stay in this workspace, never in production trees.
- No copying unreviewed Xiaomi APKs/configuration or unrelated blobs into the clean vendor tree.
- No bootloader tokens, personal IDs, modemst, persist/calibration partitions or private keys committed.
- No modifications to the local LineageOS checkout until obsolete paths are reviewed.

## After the extraction run

Review `super-metadata.txt`, `mounted-partitions.tsv`, `all-files.tsv`, `libraries.tsv`, `proprietary-candidates.txt` and candidate exclusions. Build a minimal `proprietary-files.txt`, extraction makefiles and device configuration from stock evidence. Test VINTF, SELinux, init, modules, encryption and boot integration separately before publishing production trees.

## Publishing policy

The repository secret `GH_PAT`, when present, is reserved for future **explicitly reviewed** large-file publishing from this research repository to the production repositories' `main` branches. The current acquisition/extraction workflow does **not** use it, does not commit blobs to the production trees and never creates new branches or pull requests. Device text files may be committed separately through the GitHub connector. The source archive is not itself a complete Lineage vendor tree: it is material for reviewed selection and standard Lineage extraction/makefile generation.
