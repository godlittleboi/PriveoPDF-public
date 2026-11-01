# Privacy

## Local processing

PDFs, pages, thumbnails, passwords, names, and paths remain on the device. Core
tools require no account, cloud service, or document upload.

**Recognize text (OCR)** recognizes text on the device with the system Tesseract library.
Recognized text is neither logged nor sent: it is only added to the copy that
is created. There it becomes selectable, copyable and findable by your
computer's search tools.

## Network access

Reading and editing PDFs require no connection. An update check requires a
separate action or consent and never authorizes sending a document.

## Remembered data

When restoration is enabled, PriveoPDF may locally retain open document paths,
session names, and the current selection. PDF binary content is not stored in a
session.

[Bundled Help](index.md) also works offline.

## Local protection

PDF decoding and rendering use separate processes without access to the desktop
session. Required Linux confinement applies to each worker even when the
application is already offline. This reduces the consequences of a potential
PDF engine vulnerability; it does not guarantee the absence of vulnerabilities.
Outside the launcher, some page tools retain access to the output directory. The interface
keeps the access needed to open and save your documents.

### Worker isolation on Linux

Inside the launcher, workers use Landlock (ABI 3 or newer) and the system
`libseccomp2` library. Unsupported protection stops processing. Results are
prepared privately before publication; existing files are not overwritten.
This avoids nested namespaces rejected by some AppArmor profiles. The desktop
interface still has access to your home folder; file metadata may remain
observable even where reading contents is denied.
