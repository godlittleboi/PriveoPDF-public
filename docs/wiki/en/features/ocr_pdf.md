# Recognize text (OCR)

## What it does

Make a scanned PDF searchable: the text of scanned pages is recognized on this
computer, then added invisibly. You can then search, select and copy that text
in a PDF reader.

## How to use it

Open **Recognize text (OCR)** from Home, in the **OPTIMIZE PDF** family, or use
**Tools** with an open PDF. Drop one PDF.

Tick the document's language or languages, three at most. **English**,
**French** and **Spanish** are always shown; any other language whose model is
installed joins the list. The interface language is ticked by default when its
model is installed. A greyed-out language is not installed; its tooltip gives
the command to type in a terminal, for example:

```bash
sudo apt install tesseract-ocr tesseract-ocr-eng
```

To add a language, click **ADD A LANGUAGE…**, pick it in the list (search by
name) and click **INSTALL**: the system installer asks your password and
installs the model; PriveoPDF downloads nothing itself. The language is ticked
as soon as the model is present. Without a graphical installer, **COPY THE
COMMAND** gives the command to paste in a terminal (`sudo apt install
tesseract-ocr-<code>`). Codes of common languages: `deu` German, `ita` Italian, `por`
Portuguese, `nld` Dutch, `pol` Polish, `ron` Romanian, `rus` Russian, `ara`
Arabic, `tur` Turkish, `ell` Greek, `swe` Swedish, `dan` Danish, `nor`
Norwegian, `fin` Finnish, `ces` Czech, `hun` Hungarian, `ukr` Ukrainian, `heb`
Hebrew, `jpn` Japanese, `kor` Korean, `chi_sim` Simplified Chinese, `chi_tra`
Traditional Chinese, `hin` Hindi, `vie` Vietnamese, `cat` Catalan, `eus`
Basque, `bre` Breton, `lat` Latin. Full list: `apt search tesseract-ocr-`. A
language PriveoPDF does not know is shown by its code.

When no model is installed, the button stays disabled and the same command is
shown below it. A destination file is proposed in the PDF's folder, for example
`invoice_searchable.pdf`; **CHANGE…** lets you pick another one. Click
**RECOGNIZE TEXT**. Progress is shown page by page and you can cancel.

To process only some pages (a photo or a handwritten page to leave aside, or a
document with more than 50 scanned pages), open **ADVANCED OPTIONS** and type
the pages to recognize, for example `1-50, 52`. Left empty, the field processes
every scanned page. The other pages stay as they are; a long document is
processed in several passes, by running the tool again on the file produced with
the next pages.

## Result

The result appears below the button: file created, then the number of pages made
searchable, of pages left intact (already with text, or not chosen), and of
pages where no text was found. **OPEN PDF** and **OPEN FOLDER** are offered.

Pages look exactly the same. Pages that already contain text are not modified. A
scan placed sideways or upside down is read the right way, but the page is not
rotated: use [Rotate pages](rotate.md) to straighten it. Your original stays
unchanged and an existing file is never replaced.

No file is created when every page (or every chosen page) already contains text
or when no text is recognized. Then check the ticked language and the sharpness
of the scan.

## Limits

Recognition can be wrong, especially on a blurry scan, handwriting, a complex
table or a small font: proofread important text. A page that already mixes
text and a scanned image is left as it is. Three languages at most per pass.

A document is limited to 500 pages, with at most 50 scanned A4 pages (25 in A3;
largest size A2) per pass, and to thirty minutes of processing. Beyond that,
choose the pages under **ADVANCED OPTIONS** and proceed in several passes, or
split the document with [Split PDF](split.md). Encrypted or damaged PDFs
are refused, as is a scanned page carrying an annotation, a form field or a
crop. There is no batch processing and no PDF/A conversion.

A PDF carrying a digital signature is reported as soon as it is loaded: OCR
would invalidate it. Tick **Produce a copy without the signature** to
continue; the copy no longer carries the digital signature, the original is
not modified and a visible signature remains a plain image. The box is
unticked for every new file. If the signature sits on a scanned page, that
page stays refused like any annotation.

The Tesseract models come from the system packages (Linux Mint 22, Ubuntu
24.04); PriveoPDF never downloads them.
