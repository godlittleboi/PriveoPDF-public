# Compress PDF

## What it does

Reduce a PDF's size with one simple setting. Savings depend on the document:
some files will not become smaller.

## How to use it

Open **Compress PDF** from Home or use **Tools** with an open PDF.
Drop one PDF, then choose:

- **No loss of quality**, selected by default: optimizes the file without degrading
  images or changing their resolution.
- **Stronger reduction**: also optimizes supported images with a fixed setting.
  **The quality of some images may be reduced.**

A destination file is proposed in the PDF's folder, for example
`report_compressed.pdf`; **CHANGE…** lets you pick another one. Click
**COMPRESS**. You can cancel while the operation is running.

## Result

After export, the result appears below the button: file created, original and
resulting sizes, savings and duration, with **OPEN PDF**, **OPEN FOLDER** and **CONTINUE WITH…**. Check pages, text and images. Your original
stays unchanged and an existing file is never replaced: the next destination
becomes `-2`, `-3`, and so on.

If the result is not strictly smaller, no file is created. You can change the
setting or choose another document.

An integrity-check message means export was blocked, even if the PDF opens in
a reader. One known minor defect in the internal index is accepted after the
result is verified; other warnings block export. Your original remains
unchanged in every case.

## Limits

Encrypted PDFs and documents with a detected digital signature are refused.
Empty signature fields are accepted. No minimum saving is promised. Compression
does not remove metadata, repair PDFs or add OCR. Batch processing and
resolution controls are not available. This operation does not certify PDF/A
or PDF/UA conformance.
