"""Measure the production macOS installation and fail if it exceeds size budgets."""

import argparse
import math
import os
from pathlib import Path
import platform
import stat


MIB = 1024 * 1024
DEFAULT_BUDGETS = {"executable": 15 * MIB, "bundle": 16 * MIB, "installed": 20 * MIB}


def regular_file_size(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size == 0:
        raise ValueError(f"Expected a nonempty regular file: {path}")
    return info.st_size


def tree_files(root):
    """Count regular-file logical bytes once per path; never follow symlinks."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"Expected a directory, not a symlink: {root}")

    def fail(error):
        raise error

    files = []
    for directory, _, names in os.walk(root, followlinks=False, onerror=fail):
        for name in names:
            path = Path(directory) / name
            info = path.lstat()
            if stat.S_ISREG(info.st_mode):
                files.append((path.relative_to(root), info.st_size))
    return sorted(files, key=lambda item: (-item[1], str(item[0])))


def measurements(executable, bundle, installed, baseline):
    # The app/executable are already included in the installed total; these are
    # separate views of the same installation, not values to add together.
    executable.relative_to(bundle)
    bundle.relative_to(installed)
    files = tree_files(installed)
    return {
        "executable": regular_file_size(executable),
        "bundle": sum(size for _, size in tree_files(bundle)),
        "installed": sum(size for _, size in files),
        "baseline": regular_file_size(baseline),
    }, files


def exceeded_budgets(sizes, budgets):
    return [name for name in DEFAULT_BUDGETS if sizes[name] > budgets[name]]


def format_report(sizes, files, budgets, architecture, compiler):
    labels = {"executable": "Production executable", "bundle": "Production .app bundle",
              "installed": "Current installed payload"}
    lines = ["# macOS size report", "", f"Architecture: `{architecture}`",
             f"Compiler: `{compiler.replace(chr(10), '; ')}`", "",
             "Sizes are logical bytes of regular files. Symlinks are not followed; "
             "system frameworks, the external Python runtime, settings and the retained "
             "rollback sources are outside these totals.", "",
             "| Measurement | Bytes | MiB | Budget (MiB) | Result |",
             "| --- | ---: | ---: | ---: | --- |"]
    for name, label in labels.items():
        result = "PASS" if sizes[name] <= budgets[name] else "FAIL"
        lines.append(f"| {label} | {sizes[name]:,} | {sizes[name] / MIB:.2f} | "
                     f"{budgets[name] / MIB:.2f} | {result} |")
    reduction = sizes["baseline"] - sizes["executable"]
    lines.extend(["", "Comparison executable: current source built with the previous "
                  "`-O` settings and embedded developer fixtures (`-D AI_STATUS_SMOKE`), "
                  "then ad-hoc signed without stripping.", "",
                  f"Baseline: {sizes['baseline']:,} bytes ({sizes['baseline'] / MIB:.2f} MiB). "
                  f"Production reduction: {reduction:,} bytes ({reduction / MIB:.2f} MiB, "
                  f"{100 * reduction / sizes['baseline']:.1f}%).", "",
                  "This is a same-source/compiler comparison, not a historical release "
                  "measurement or a compressed download size.", "",
                  "Largest files in the current installed payload:", "",
                  "| File | Bytes | MiB |", "| --- | ---: | ---: |"])
    for path, size in files[:10]:
        lines.append(f"| `{path}` | {size:,} | {size / MIB:.2f} |")
    return "\n".join(lines) + "\n"


def mib_budget(value):
    number = float(value)
    if not math.isfinite(number) or number * MIB < 1:
        raise argparse.ArgumentTypeError("Budget must be finite and at least one byte")
    return int(number * MIB)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("executable", "bundle", "installed", "baseline-executable", "report"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--summary", type=Path,
                        default=Path(os.environ["GITHUB_STEP_SUMMARY"])
                        if os.environ.get("GITHUB_STEP_SUMMARY") else None)
    parser.add_argument("--architecture", default=platform.machine())
    parser.add_argument("--compiler", required=True)
    for name, default in DEFAULT_BUDGETS.items():
        parser.add_argument(f"--max-{name}-mib", type=mib_budget, default=default)
    args = parser.parse_args()
    try:
        sizes, files = measurements(args.executable, args.bundle, args.installed,
                                    args.baseline_executable)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Cannot measure macOS installation: {error}\n")
    budgets = {name: getattr(args, f"max_{name}_mib") for name in DEFAULT_BUDGETS}
    report = format_report(sizes, files, budgets, args.architecture, args.compiler)
    print(report, end="")
    args.report.write_text(report, encoding="utf-8")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as summary:
            summary.write(report)
    failed = exceeded_budgets(sizes, budgets)
    if failed:
        parser.exit(1, "macOS size budget exceeded: " + ", ".join(failed) + "\n")


if __name__ == "__main__":
    main()
