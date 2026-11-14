#!/usr/bin/env python3
"""Find repeated installed-target Make rules before another expensive Kati pass.

Reads the *already generated* out/soong/installs-lineage_mist.mk.
No source sync, Soong regeneration, or build is performed.
"""
import argparse
from collections import defaultdict
from pathlib import Path
import re

def main():
    p = argparse.ArgumentParser()
    p.add_argument("makefile", type=Path)
    p.add_argument("--output", type=Path, default=Path("/tmp/mist-all-duplicate-targets.txt"))
    a = p.parse_args()
    if not a.makefile.is_file():
        p.error("Makefile not found: " + str(a.makefile))
    # Do not treat ordinary dependency-only rule repetitions as proven
    # duplicate *commands*. Check for a tab-indented recipe per rule.
    entries = defaultdict(list)
    pattern = re.compile(r"^(out/target/product/[^:\s]+):(?:\s|$)")
    previous = None
    lineno = 0
    with a.makefile.open(errors="replace") as fh:
        for line in fh:
            lineno += 1
            match = pattern.match(line)
            if match:
                target = match.group(1)
                previous = {"line": lineno, "definition": line.rstrip()[:450],
                            "recipe": False, "command": ""}
                entries[target].append(previous)
                continue
            # A recipe immediately following a declaration (or its blank
            # separator) belongs to that declaration. Other nonblank text
            # terminates that candidate.
            if previous is not None:
                if line.startswith("\t"):
                    previous["recipe"] = True
                    if not previous["command"]:
                        previous["command"] = line.strip()[:450]
                elif line.strip() and not line[:1].isspace():
                    previous = None
    repeats = [(name, values) for name, values in entries.items() if len(values) > 1]
    certain = [(name, vals) for name, vals in repeats if sum(x["recipe"] for x in vals) >= 2]
    candidates = [(name, vals) for name, vals in repeats if sum(x["recipe"] for x in vals) < 2]
    def format_section(title, rows):
        lines = [title, "=" * len(title)]
        for name, values in sorted(rows):
            lines.append("\nTARGET: " + name)
            for v in values:
                lines.append("  line " + str(v["line"]) + (" [RECIPE]" if v["recipe"] else " [dependency only/unknown]"))
                lines.append("    " + v["definition"])
                if v["command"]:
                    lines.append("    command: " + v["command"])
        return "\n".join(lines)
    report = ("Makefile: " + str(a.makefile) + "\n"
              + "Unique installed targets: " + str(len(entries)) + "\n"
              + "Targets with 2+ rule declarations: " + str(len(repeats)) + "\n"
              + "Targets with 2+ detected recipes (definite conflicts): " + str(len(certain)) + "\n\n"
              + format_section("CONFIRMED DUPLICATE RECIPES", certain) + "\n\n"
              + format_section("OTHER REPEATED DECLARATIONS (review only)", candidates) + "\n")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(report)
    print(f"Scanned {lineno:,} lines; {len(certain)} definite conflicting target(s), "
          f"{len(candidates)} other repeated rule target(s).")
    print("Full report:", a.output)
    print("Conflicting targets:")
    for name, _ in sorted(certain):
        print("  " + name)
    if not certain:
        print("No confirmed repeated recipes; inspect 'other repeated declarations' "
              "in the report for unusual generated Make rule layouts.")

if __name__ == "__main__":
    main()
