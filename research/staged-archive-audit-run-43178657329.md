# Mist stock vendor/boot archive audit — GitHub Actions run 43178657329

**Date:** 2026-11-12 UTC. **Outcome:** SUCCESS.

- Workflow: https://github.com/nobodyAtall-code/copilot_project/actions/runs/43178657329
- Job: https://github.com/nobodyAtall-code/copilot_project/actions/runs/43178657329/job/131048972234
- Workflow commit at execution: `3df9275a715067e5f86a0b354366d14ec9db1feb`
- Audit artifact: `mist-staged-archive-audit`, ID `13924823795`, 278,442-byte zip, uploaded successfully.
- `stock-vendor-source.tar.zst`: SHA256 verification PASS.
- `boot.img`, `dtbo.img`, `init_boot.img`, `recovery.img`, `vbmeta.img`, `vbmeta_system.img`, `vendor_boot.img`: SHA256 verification PASS.
- Research script output: **4,373 archive entries** and **7 boot images** inspected.
- Upload action reported **360 files** in artifact; this includes selected-stock-config and audit reports, not an approved vendor manifest.
- Nonfatal warnings: `SyntaxWarning: invalid escape sequence '\\`'` in the Markdown report generator (fixed in a later commit), Node.js deprecations from third-party Actions.

## Gates that remain

The successful workflow establishes archive integrity and inventory generation, **not** correctness of each VINTF/RC/fstab/module entry. Inspect the actual artifact's `audit.json`, `interesting-paths.txt` and `selected-stock-config/` before selecting any production blobs. Verify filesystem link targets and original SELinux labels, stock kernel module compatibility, boot ramdisk content, full lpdump group capacities, and HAL dependencies.

The artifact was downloaded through the GitHub connector for further inspection, but local processing of its contents was unavailable during this review. Therefore its detailed content is **not yet audited** here. Do not invent its per-partition counts, inferred boot header structure, or runtime device functionality.

Production vendor/kernel-prebuilt trees remain intentionally unchanged; no ROM build or flash has been tested. All research tooling stays in `copilot_project`.
