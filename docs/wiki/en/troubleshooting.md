# Troubleshooting

## A PDF does not open

Check that it still exists, ends with `.pdf`, and opens in another application.
A protected or damaged document may be refused.

In a tool, an unusable PDF is reported as soon as it is loaded, below the
source, and the action button stays disabled:

- “This PDF is password-protected.”: **UNLOCK PDF** opens Unlock PDF on that
  file. A PDF that opens without a password but carries usage restrictions is
  processed normally; the copy no longer has those restrictions;
- “This PDF is unreadable or damaged.”: choose another file with
  **CHANGE PDF**.

In Merge and Insert, the message names each file in question.

## An operation does not start

Check the page selection, highlighted fields, and destination. Output must differ
from the source and must not already exist. The reason appears below the button.

Typed page ranges accept only the digits 0 to 9, hyphens, and commas (for example
`1-3,5`). A page number cannot exceed 100,000, and an expression cannot add up to
more than 100,000 pages.

## "The structure of this PDF is too large for this tool"

Merge, Split, Extract, Remove, Reorder, Insert and Add a blank page read the
resources of the copied pages to keep the state of the layers. A document with
exceptionally many resources (several hundred thousand objects for a single
operation) is refused before anything is written, with no file created. Process
fewer pages at a time: extract or split the document into smaller parts, then
run the tool again on each part. The original is never modified.

## The result is unexpected

Keep the original, record the action, and retry with a non-sensitive copy. Then
read the [tool sheet](features/README.md) to check its limits.

## Recognize text (OCR) recognizes nothing or stays disabled

The button stays disabled until a language model is installed. In a terminal:
`sudo apt install tesseract-ocr tesseract-ocr-eng` (`-fra` for French, `-spa`
for Spanish), then reopen the tool. When no text is recognized, tick the right
language and use a sharper scan. See [Recognize text (OCR)](features/ocr_pdf.md).

## OCR or the photocopy could not run under its memory protection

The message ends with a **Technical detail** you can copy. These tasks limit
their memory on the computer: they need a user systemd session, cgroups v2
and bubblewrap. When these are present, the document may have exceeded the
processing limit: try a shorter document. No file is created in this case.

## The display is difficult to read

Choose another theme under **Settings → Theme** and see
[Appearance](features/appearance.md).

No report or document is sent automatically.

## The public source snapshot will not start

Install its locked dependencies, then use `bash tools/launch_priveopdf.sh` from
the project root. A direct Python launch does not prepare the sandbox.
`network_isolation_unavailable` means required Linux isolation is unavailable;
keep its diagnostic and check the prerequisites in the included source
installation guide. Do not disable sandboxing to process a PDF.

Private Git updates and internal beta history are disabled in public snapshots.
Private beta checklists and their launcher tools belong to the maintainer's
separate development workflow.
