# Redact PDF

## What it does

Black out areas of a PDF (a name, a number, an address, a photo) and really
remove what was underneath, before sharing the file. A rectangle drawn on top
is not enough: the hidden text stays in the file and comes back when copied.
Here, the output is a photocopy of every page with the areas blacked out, then
verified.

## How to use it

Open **Redact PDF** from the home screen, **SECURE PDF** family, or from an
open PDF with **Tools**. Drop a single PDF.

The pages are shown on the left. Draw a rectangle with the mouse over each
area to black out: it appears in colour on the page and the area counter on
the right grows. **Remove the last area** cancels the last rectangle, **Clear
all** removes them all. Ctrl + wheel sets the zoom.

A destination file is proposed in the PDF's folder, for example
`contract_redacted.pdf`; **CHANGE…** picks another one. Click **REDACT THE
PDF**. Progress is shown page by page.

## Result

The result is shown under the button: file created, number of blacked-out
areas and of pages concerned, then what the verification established after
writing: every page is an image, no text and no hidden object remains. **OPEN
PDF** and **OPEN FOLDER** are offered. The original is unchanged and an
existing file is never replaced.

In the output, every page is an image of the original page, blacked-out areas
included, at 200 dots per inch. Text is therefore no longer selectable nor
searchable: to make it searchable, run [Recognize text (OCR)](ocr_pdf.md) on
the output; nothing is recognized under the black areas. Metadata, links,
forms, attachments and layers of the original are not carried over; a stamp
or a filled field stays visible, as on a photocopy, and is blacked out like
the rest of the page.

## Limits

The output is heavier than a text PDF and its text is no longer selectable.
Areas are rectangles; draw several for a complex shape. Redaction refuses a
protected or damaged PDF, an interactive form and a document beyond
500 pages or about 20 million pixels per page. At most 500 areas per document.

A PDF carrying a digital signature is reported as soon as it is loaded:
redaction would invalidate it. Tick **Produce a copy without the signature**
to continue; the copy no longer carries the digital signature, the original is
not modified and a visible signature remains a plain image. The box is
unticked for every new file.

Check the output yourself before sharing it: the verification establishes
that the drawn areas are black and that no text remains, not that you drew
every useful area.
