"""Download proper-quality brand logos for the 18 industry-page companies.

Why this script exists: company logo files live in this folder (/public/logos/)
and each company's markdown in /src/content/companies/ already references the
filename it expects. But the folder started empty. Real brand logos come from
Clearbit's Logo API, which is reachable from residential IPs but blocked from
some sandboxes. Easiest path: run this from Ella's (or Smadar's) own machine.

Run from the repo root:
    cd site
    python public/logos/_download-logos.py

Output: ~18 PNGs in this folder, named exactly as the markdowns reference.
Run again any time the company list changes. Existing files are overwritten
(comment out the `urlretrieve` line below to make it skip existing files).

Fallback: for the rare company Clearbit doesn't have, the script prints
the company name and you'll need to manually grab a logo (right-click
save-image on the company's About page is usually the fastest path).
"""

import os
import urllib.request
import urllib.error

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# (filename, clearbit-domain) per company. Filenames match what the markdowns
# in /src/content/companies/ reference.
COMPANIES = [
    # Faculty-founded
    ("mobileye.png",   "mobileye.com"),
    ("ai21-labs.png",  "ai21.com"),
    ("orcam.png",      "orcam.com"),
    ("factify.png",    "factify.io"),
    ("lightricks.png", "lightricks.com"),
    ("starkware.png",  "starkware.co"),
    ("briefcam.png",   "briefcam.com"),
    # Industry partners (mobileye/lightricks/starkware are reused, downloaded once)
    ("apple.png",       "apple.com"),
    ("intel.png",       "intel.com"),
    ("google.png",      "google.com"),
    ("monday.png",      "monday.com"),
    ("kla.png",         "kla.com"),
    ("rsip-vision.png", "rsipvision.com"),
    ("queenb.png",      "queenb.org.il"),
    ("forstart.png",    "forstart.org.il"),
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

def fetch(url: str, dest: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        if len(data) < 100:
            return False
        with open(dest, "wb") as f:
            f.write(data)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return False

success, failed = [], []
for filename, domain in COMPANIES:
    dest = os.path.join(OUT_DIR, filename)
    # Try Clearbit first (proper brand logo, transparent PNG).
    if fetch(f"https://logo.clearbit.com/{domain}", dest):
        success.append(filename)
        print(f"  ok  {filename:24}  <- clearbit/{domain}")
        continue
    # Fallback: Google favicon at 128px (lower quality but at least an image).
    if fetch(f"https://www.google.com/s2/favicons?sz=128&domain={domain}", dest):
        success.append(filename + " (favicon fallback)")
        print(f"  fav {filename:24}  <- google-favicon/{domain}")
        continue
    failed.append((filename, domain))
    print(f"  --  {filename:24}  no source worked; grab manually from https://{domain}")

print()
print(f"Done. {len(success)} downloaded, {len(failed)} need manual handling.")
if failed:
    print("Manual:")
    for filename, domain in failed:
        print(f"  {filename}  <-  https://{domain}")
