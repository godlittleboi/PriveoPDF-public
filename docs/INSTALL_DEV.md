# Run the public sources

These instructions apply to this public snapshot, on Linux Mint 22 or Ubuntu
24.04, with Python 3.12 or later. Run commands from the directory containing
`pyproject.toml`. The snapshot does not include the private development
installer, beta manager or release-building scripts.

## Prerequisites

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) using its
official instructions, then install the native Linux dependencies:

```bash
sudo apt update
sudo apt install python3 python3-venv bubblewrap libegl1 libgl1 \
  libxkbcommon-x11-0 libxcb-cursor0
```

A graphical desktop session is required for normal use. OCR and protected image
rendering need a working user systemd session and cgroups v2. For English OCR:

```bash
sudo apt install tesseract-ocr tesseract-ocr-eng
```

Install additional Tesseract language packages as needed, such as
`tesseract-ocr-fra` for French. The application uses local models.

## Install and launch

```bash
uv sync --frozen --dev
bash tools/launch_priveopdf.sh
```

To open a document directly:

```bash
bash tools/launch_priveopdf.sh /path/to/document.pdf
```

Dependency installation uses the network. PDF processing uses the Linux
launcher, which prepares the document sandbox and local helper processes.
Do not replace it with a direct `uv run priveopdf` launch.

If `network_isolation_unavailable` appears, check that Bubblewrap is installed
and permitted to create namespaces on this system:

```bash
bwrap --die-with-parent --unshare-net --ro-bind / / -- /bin/true
```

A nonzero result means this environment cannot run the required isolation.
Keep the diagnostic and resolve the system configuration; do not disable the
application's protections. A container may lack these system facilities.

## Review and build

Check an untouched snapshot before installing dependencies:

```bash
sha256sum --check SHA256SUMS
python3 tools/check_public_source_contract.py --snapshot . --technical-only --repository-checkout
```

After installation:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
QT_QPA_PLATFORM=offscreen uv run pytest
uv build
```

`uv build` produces Python source and wheel packages, not an installable Linux
`.deb`. The included tests are a public subset; passing them does not certify
all PDF operations or replace a real desktop qualification. Integrity checks
apply to the published snapshot, and will intentionally reject edited files.

Private Git updates and internal beta switching are disabled. To update this
source installation, obtain a new published snapshot and follow these steps in
a separate directory. See [the user guide](wiki/en/getting-started.md) for tools
and [the package guide](INSTALL_USER.md) for official binary releases.
