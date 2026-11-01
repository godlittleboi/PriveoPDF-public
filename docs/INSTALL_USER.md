# Linux package installation

The first installable `.deb` beta is still in preparation. There is currently no
public binary release to download. Public source snapshots can be inspected and
run using the [source installation guide](INSTALL_DEV.md).

Official packages will be published only in
[PriveoPDF Releases](https://github.com/godlittleboi/PriveoPDF-public/releases),
with their version, supported systems, checksums and verification instructions.
Linux Mint 22 and Ubuntu 24.04 on Intel/AMD 64-bit PCs are the target systems.

When a package is available, follow the instructions for that exact release,
verify its published checksums and signature, then open the `.deb` with the
system package manager. PriveoPDF will appear in the application menu. The
release-signing key fingerprint will be listed in [SECURITY.md](../SECURITY.md).

Updates require installing a newer official package. Removing the package
preserves your PDF files and preferences. Mandatory Linux isolation must be
available for the application to start.

The source snapshot contains no `install_priveopdf.sh`, desktop installer or
uninstaller. Its Python wheel is not a replacement for the official `.deb`.
