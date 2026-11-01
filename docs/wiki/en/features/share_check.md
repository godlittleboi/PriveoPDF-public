# Check before sharing

## What it does

Inspect Info and XMP properties without modifying the file, then choose to
remove global metadata or rebuild pages as images. Both values remain visible
when Info and XMP disagree.

## How to use it

Open **Check before sharing** from Home or **Tools**, then select a PDF. A
sentence sums up the inspection, then an **Item · In this PDF · To do** table
lists the metadata found (title, author, dates…) and the items to review
(links, comments, attachments…), with the useful action. **Technical
details** (folded) shows Info, XMP and every raw property. Incomplete analysis reports
lower bounds: zero does not then establish absence. Its cause appears on the
next line (unreadable file, inspection limit reached, time limit exceeded…).

For an already open document, **Tools → Check before sharing** starts inspection
automatically. When switching documents quickly, the report describes the last
selected document. **Cancel** or leaving the page stops inspection and any pending
restart; returning to the tool starts inspection again.

**Remove metadata** is selected by default. A copy `<name>_no-metadata.pdf` is
proposed (**CHANGE…** for another destination); run the action. If no global containers exist, no file is created; photocopy remains
available.

For **Photocopy PDF — images only**, read the warning and prepare the preview.
Browse pages and zoom to check small text. The preview shows the rebuilt PDF
using the same settings as export. Until the preview is ready, the button stays greyed out with the reason below
it. A copy `<name>_photocopy.pdf` is proposed; click **CREATE PHOTOCOPY**. Cancel during rendering or verification. A changed source requires
a new preview. Unsupported form appearances are refused.

A copy is created by default. **Replace this PDF** requires confirmation for
every operation, including a reminder of lost text and interactive features
for photocopy. The original remains intact until successful publication.

## Result

The result appears below the button, with sizes before and after. Inspection
is recalculated from the result. **OPEN PDF** opens the PDF and **OPEN FOLDER**
its folder.
Standard mode removes global Info and XMP while preserving text, annotations,
links, forms and attachments. Photocopy keeps page images only: no selectable
text, OCR or original hidden objects. Filenames and visible information are
not anonymized.

## Limits

Candidate fix #284 adapts memory protection to the Beta launcher.
Photocopy still requires validation on Linux Mint: preview, export, cancellation
and memory limits. Only tick checks actually performed in Beta.

Photocopy requires Linux 6.5+, user systemd 255+, libsystemd0, cgroups v2,
bubblewrap and the launcher's Landlock/seccomp protections.
If memory protection is unavailable or the budget is reached, no output is
published. Windows is not qualified.
The profile uses colour, 200 dpi and lossless compression; size may increase
and sharpness decrease at high zoom. Limits: 500 pages, 20 million pixels per
page, 256 MiB of total pixels, 1.5 GiB group memory, no swap and 120 seconds per
operation. Reaching a limit never silently reduces quality. Applied signatures
prevent transformations; inspection remains available. Unlock encrypted PDFs
using the existing tool.
No PDF/A or PDF/UA compliance, general safety or anonymity is certified.
Private temporary files are cleaned up; physical secure erasure from disk or
backups is not promised.
