#!/usr/bin/env python3
"""Download Xiaomi ROM byte ranges concurrently across verified mirrors."""
import concurrent.futures as cf
import hashlib
import os
import re
import threading
import time
import urllib.request
from pathlib import Path

HOSTS = (
    "bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com",
    "cdn-ota.azureedge.net",
    "cdnorg.d.miui.com",
    "bn.d.miui.com",
    "hugeota.d.miui.com",
    "bigota.d.miui.com",
)
PART = 32 * 1024 * 1024
PROBE = 2 * 1024 * 1024
TOTAL_RE = re.compile(r"bytes (\d+)-(\d+)/(\d+)")


def ranged(url, start, end, timeout):
    req = urllib.request.Request(url, headers={
        "Range": f"bytes={start}-{end}",
        "Accept-Encoding": "identity",
        "User-Agent": "mist-firmware-downloader/1.0",
    })
    response = urllib.request.urlopen(req, timeout=timeout)
    header = response.headers.get("Content-Range", "")
    match = TOTAL_RE.fullmatch(header.strip())
    if response.status != 206 or not match or (int(match[1]), int(match[2])) != (start, end):
        response.close()
        raise ValueError(f"Invalid HTTP range response: {response.status}, {header}")
    return response, int(match[3])


def probe(url):
    begin = time.monotonic()
    try:
        response, size = ranged(url, 0, PROBE - 1, 18)
        with response:
            data = response.read(PROBE + 1)
        if len(data) != PROBE:
            raise IOError("Probe returned incorrect byte count")
        speed = len(data) / max(time.monotonic() - begin, 0.01)
        return (url, size, speed, "OK")
    except Exception as exc:
        return (url, 0, 0, str(exc)[:160])


def main():
    name = "mist_global_images_OS3.0.304.0.WPUMIXM_20260917.0000.00_16.0_global_c4450c4e16.tgz"
    relative = "OS3.0.304.0.WPUMIXM/" + name
    expected = "c4450c4e168052ca9de1211306d3beff"
    output = Path("work") / name
    output.parent.mkdir(parents=True, exist_ok=True)
    Path("reports").mkdir(exist_ok=True)
    urls = ["https://" + host + "/" + relative for host in HOSTS]
    print("Probing Singapore, Azure, and Xiaomi CDN mirrors in parallel", flush=True)
    with cf.ThreadPoolExecutor(max_workers=len(urls)) as pool:
        measurements = list(pool.map(probe, urls))
    with open("reports/cdn-probes.tsv", "w") as report:
        report.write("url\tstatus\tsize\tspeed_bytes_per_sec\n")
        for url, size, speed, status in measurements:
            report.write(f"{url}\t{status}\t{size}\t{speed:.0f}\n")
            print(f"{url.split('/')[2]}: {status}, {speed / 1048576:.2f} MiB/s", flush=True)
    good = sorted([m for m in measurements if m[3] == "OK"], key=lambda m: m[2], reverse=True)
    if not good:
        raise RuntimeError("No mirror supports verified HTTP byte ranges; check report")
    total = good[0][1]
    good = [m for m in good if m[1] == total]
    if not good:
        raise RuntimeError("Mirrors disagree on archive size")
    # Use performant mirrors first; slower verified hosts remain fallback choices.
    fast = [m for m in good if m[2] >= good[0][2] * 0.35][:4]
    fallback = [m[0] for m in good]
    print(f"Using {len(fast)} fast mirrors; {len(fallback)} total fallback mirrors; {total} bytes", flush=True)
    ranges = [(start, min(start + PART - 1, total - 1)) for start in range(0, total, PART)]
    fd = os.open(output, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
    lock = threading.Lock()
    done_bytes = 0
    done_parts = 0
    try:
        os.ftruncate(fd, total)

        def worker(item):
            nonlocal done_bytes, done_parts
            begin, end = item
            first = (begin // PART) % len(fast)
            selected = [m[0] for m in fast[first:] + fast[:first]]
            selected += [url for url in fallback if url not in selected]
            error = ""
            for trial in range(3):
                for url in selected:
                    try:
                        response, size = ranged(url, begin, end, 60)
                        if size != total:
                            response.close()
                            raise ValueError("Inconsistent full-file size")
                        written = 0
                        with response:
                            while written < end - begin + 1:
                                data = response.read(min(1024 * 1024, end - begin + 1 - written))
                                if not data:
                                    break
                                offset = 0
                                while offset < len(data):
                                    n = os.pwrite(fd, data[offset:], begin + written + offset)
                                    if n == 0:
                                        raise IOError("pwrite returned 0")
                                    offset += n
                                written += len(data)
                        if written != end - begin + 1:
                            raise IOError(f"Short response: {written}")
                        with lock:
                            done_bytes += written
                            done_parts += 1
                        return
                    except Exception as exc:
                        error = f"{url.split('/')[2]}: {exc}"
                time.sleep(2 ** trial)
            raise RuntimeError(f"Chunk {begin}-{end} failed: {error}")

        start_time = time.monotonic()
        print(f"Starting 16 parallel range workers for {len(ranges)} segments", flush=True)
        with cf.ThreadPoolExecutor(max_workers=16) as pool:
            futures = [pool.submit(worker, segment) for segment in ranges]
            pending = set(futures)
            while pending:
                finished, pending = cf.wait(pending, timeout=30, return_when=cf.FIRST_COMPLETED)
                for result in finished:
                    result.result()
                with lock:
                    count, received = done_parts, done_bytes
                elapsed = max(time.monotonic() - start_time, 0.1)
                print(f"{count}/{len(ranges)} chunks ({received / total:.1%}), {received / elapsed / 1048576:.2f} MiB/s aggregate", flush=True)
        os.fsync(fd)
    finally:
        os.close(fd)

    checksum = hashlib.md5()
    with output.open("rb") as image:
        for piece in iter(lambda: image.read(8 * 1024 * 1024), b""):
            checksum.update(piece)
    digest = checksum.hexdigest()
    Path("reports/firmware.md5").write_text(f"{digest}  {output}\n")
    if digest != expected:
        output.unlink(missing_ok=True)
        raise RuntimeError(f"MD5 mismatch: {digest} != {expected}. Invalid archive deleted.")
    Path("reports/source.txt").write_text(f"firmware={relative}\nmd5={digest}\nsize={total}\n")
    print("Verified firmware MD5:", digest, flush=True)


if __name__ == "__main__":
    main()
