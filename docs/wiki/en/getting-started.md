# Getting started

The menu shows **PriveoPDF** separately from **PriveoPDF DEV** and the internal beta, with the official logo included in the package.

If the left sidebar is collapsed, click its logo or the three-line handle to
restore the full wordmark and privacy panel. DEV and the public package may
share their theme and collapsed sidebar preference while running different
versions.

## Linux installation

The first installable `.deb` beta for Ubuntu 24.04 / Linux Mint 22 (64-bit) is
still in preparation. Official downloads, when available, will appear in
[Releases](https://github.com/godlittleboi/PriveoPDF-public/releases), alongside
verification instructions. Public sources and an installable release are
separate distributions.

For a public source snapshot, follow the installation guide included in its
`docs/INSTALL_DEV.md`. Launch from its root using
`bash tools/launch_priveopdf.sh` after installing dependencies. Private DEV
shortcut installers and internal beta tools are not part of that snapshot.

After installing a validated package, **PriveoPDF** appears in the application menu. In a `.deb` installation, **Check for updates** queries only the public `PriveoPDF-public` Releases after your confirmation. When a newer version is detected, PriveoPDF shows its notes and lets you open that exact Release page; you then install the new `.deb` over the existing package with the system package manager. The private development Git updater is never used by the public package.

Removing the package preserves your documents and preferences. Launch is refused when mandatory network isolation is unavailable.

## Open a PDF

Drop a file on the home screen or choose **View PDF**. Once opened, the
document also appears under **Open documents**.

In a tool, you can drop a PDF anywhere on the window: it becomes the source of
the tool on screen. **Change PDF** and **Add PDF** open the file picker directly,
in the last folder you used.

## Edit a PDF

1. Choose the tool that matches your goal.
2. Select the local PDF or PDFs.
3. Set the required pages or options.
4. Check the proposed output: a new file, never an existing one.
5. Start the operation. The tool stays on screen with the result: file
   created, size, page count when known and folder.
6. Choose what comes next: **Open PDF**, **Open folder** or **Continue
   with…**, which opens another tool on the created file. The created file
   joins **Open documents** only through one of these actions; otherwise the
   next tool keeps working on your own file.

With the keyboard, in a tool, **Ctrl+Enter** starts the operation when it is
possible and **Escape** goes back. **Ctrl+K** opens the tool list.

The home screen groups tools by family. With one open PDF, it recommends
**View PDF**; with 2 to 4 readable PDFs, **Merge PDF**. A password-protected
PDF is marked **[protected]** under **Open documents** once a tool or the viewer
has tried to open it; the home screen then recommends **Unlock PDF**.

See [the sixteen available tools](features/README.md) to choose the right workflow.
If something blocks you, open [Troubleshooting](troubleshooting.md).
