# Linux package installation

[Download the latest stable Debian package](https://github.com/godlittleboi/PriveoPDF-public/releases/latest/download/priveopdf_amd64.deb)
for Linux Mint 22.x or Ubuntu 24.04 on a 64-bit Intel or AMD PC.

Follow the instructions in the [release notes](https://github.com/godlittleboi/PriveoPDF-public/releases/latest),
verify the published checksums and signature, then open the `.deb` with the
system package manager. PriveoPDF will appear in the application menu. The
release-signing key fingerprint is listed in [SECURITY.md](../SECURITY.md).

Updates require installing a newer official package. Removing the package
preserves your PDF files and preferences. Mandatory Linux isolation must be
available for the application to start.

The source snapshot contains no `install_priveopdf.sh`, desktop installer or
uninstaller. Its Python wheel is not a replacement for the official `.deb`.
