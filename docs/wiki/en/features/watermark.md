# Watermark PDF

## What it does

Write a visible text on every page of a PDF before handing it over: a notice
("Confidential", "Non-binding copy"), the recipient's name, a reference. If
the file travels, the copy says where it came from. The text is written into
the content of every page, not added as an annotation a viewer removes with
one click.

## How to use it

Open **Watermark PDF** from the home page, family **SECURE PDF**, or from an
open PDF with **Tools**. Drop a single PDF.

The pages show on the left. On the right, enter the **Text** (up to 120
characters: Latin letters with accents, digits, common punctuation), choose
the **Layout** — diagonal and centered, or repeated over the page — and the
**Strength** (light, medium, strong). The preview updates on the pages with
every change. Ctrl + wheel sets the zoom.

A destination file is proposed at once in the PDF's folder, for example
`contract_watermarked.pdf`; **CHANGE…** picks another. Click **WATERMARK THE
PDF**.

## Result

The result shows under the button: file created, then what the verification
established after writing: the text is present and visible on every page.
**OPEN THE PDF** and **OPEN THE FOLDER** are offered. The original stays
unchanged and an existing file is never replaced.

In the output, the original text stays selectable and searchable; so does
the watermark. Links, forms, annotations and metadata of the original are
kept as they are. The verification reopens the output, counts its pages,
checks that no annotation was added, finds the text on every page and
compares every rendered page with the original page.

## Limits

No visible watermark is indelible: someone who re-edits the PDF or turns it
into images can remove it. The promise is resistance to trivial removal, not
copy protection. The watermark refuses a protected or damaged PDF and
a document beyond 500 pages. The text uses a standard font (Helvetica-Bold):
characters outside the Latin alphabet are refused before the action.

A PDF carrying a digital signature is reported as soon as it is loaded: the
watermark would invalidate it. Tick **Produce a copy without the signature**
to continue; the copy no longer carries the digital signature, the original is
not modified and a visible signature remains a plain image. The box is
unticked for every new file.
