#!/usr/bin/env python3
"""
Master generator: downloads source data if missing, then generates all TTL files.

Usage:
    python generators/generate_all.py          # generate all
    python generators/generate_all.py --clean  # re-download CSVs first

Source CSVs are cached in csv/ and only downloaded when missing.
Tabel 35 (autorisatietabel) must be placed manually as xlsx.
"""

import os
import subprocess
import sys
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR = os.path.join(BASE_DIR, "csv")
TTL_DIR = os.path.join(BASE_DIR, "ttl")
GEN_DIR = os.path.join(BASE_DIR, "generators")

# RvIG download URLs for Landelijke Tabellen
DOWNLOADS = {
    "tabel32_nationaliteit.csv": "https://publicaties.rvig.nl/media/13304/download",
    "tabel33_gemeente.csv": "https://publicaties.rvig.nl/media/13307/download",
    "tabel34_land.csv": "https://publicaties.rvig.nl/media/13309/download",
    "tabel35_autorisatietabel.csv": "https://publicaties.rvig.nl/media/13305/download",
    "tabel56_verblijfstitel.csv": "https://publicaties.rvig.nl/media/13318/download",
}

# Generators in execution order
GENERATORS = [
    "generate_tabellen.py",
    "generate_informatiemodel.py",
    "generate_afnemers.py",
    "generate_autorisatiebesluiten.py",
    "generate_autorisatiebesluiten_compact.py",
    "generate_dcat.py",
    "validate.py",
]


def download_csv(filename, url):
    """Download a CSV file if it doesn't exist."""
    path = os.path.join(CSV_DIR, filename)
    if os.path.exists(path):
        return
    print(f"  Downloading {filename}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "brp-odrl-generator"})
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
        os.makedirs(CSV_DIR, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        print(f"    Saved ({len(data)} bytes)")
    except Exception as e:
        print(f"    FAILED: {e}")
        print(f"    Download manually from {url}")
        sys.exit(1)


def ensure_sources(clean=False):
    """Ensure all source files are present."""
    os.makedirs(CSV_DIR, exist_ok=True)

    if clean:
        for filename in DOWNLOADS:
            path = os.path.join(CSV_DIR, filename)
            if os.path.exists(path):
                os.remove(path)
                print(f"  Removed cached {filename}")

    print("Checking source data...")
    for filename, url in DOWNLOADS.items():
        download_csv(filename, url)
    print("  All sources present.\n")


def run_generator(script):
    """Run a generator script."""
    path = os.path.join(GEN_DIR, script)
    print(f"Running {script}...")
    result = subprocess.run(
        [sys.executable, path],
        cwd=GEN_DIR,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            print(f"  {line}")
    if result.returncode != 0:
        print(f"  FAILED (exit code {result.returncode})")
        if result.stderr:
            for line in result.stderr.strip().split("\n"):
                print(f"  {line}")
        sys.exit(1)
    print()


def clean_ttl():
    """Remove all generated TTL files."""
    os.makedirs(TTL_DIR, exist_ok=True)
    for fn in os.listdir(TTL_DIR):
        if fn.endswith(".ttl"):
            os.remove(os.path.join(TTL_DIR, fn))


def main():
    clean = "--clean" in sys.argv
    clean_ttl()
    ensure_sources(clean=clean)
    for script in GENERATORS:
        run_generator(script)
    print("All TTL files generated successfully.")


if __name__ == "__main__":
    main()
