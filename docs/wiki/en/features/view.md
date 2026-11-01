# View PDF

## What it does

Read a PDF, browse its pages, and check its content without changing it.

## How to use it

Drop a PDF or select **Browse**. The mouse wheel and trackpad scroll smoothly
through the document. Up/Down scroll; Page Up/Down move one screen. Use the
page controls or thumbnail drawer to jump directly to a page. **Ctrl + wheel**
changes zoom, centred on the pointer: the spot you aim at stays under the
mouse. The page keeps its display while the new rendering arrives, with no
blank page in between; **Fit** adjusts the page or its width to the window. On a new
installation, a PDF opens fitted to the width; an updated installation keeps
its setting (**Settings → PDF reading**). The file name appears at the top of the window.
The **+** and **−** buttons change zoom by 5 percentage points per click.
Manual zoom ranges from 1% to 400%; **Fit** may use a different value to
display an unusually sized page in full.
Reading mode (**More**, or **Ctrl+Shift+R**; **Escape** to leave it) fits the width; when it ends, the
zoom chosen before comes back.

To copy text, drag the mouse over the lines you want, as in an ordinary PDF
reader: the drag may start or end in the margin, and the highlight follows the
text. **Ctrl+C** copies the selection; clicking elsewhere clears it. Over text,
the pointer becomes a vertical bar.

To find a word, press **Ctrl+F** or select the magnifier, then type the text:
the whole document is searched. Results are highlighted; **Enter** goes to the
next one, **Shift+Enter** to the previous one, and the counter shows the
position, for example `2 / 5`. **Esc** closes the search.

## Result

The PDF remains open in the application and appears under **Open documents**.
No new file is created.

## Limits

A protected, damaged, or unusual PDF may fail to open or render only partially.
Viewing never starts text recognition automatically: a scanned PDF, made of
images, has no text to select or search. [Recognize text (OCR)](ocr_pdf.md) makes a copy
whose text can be selected and searched. Selection stays on a single page.
Search ignores letter case but not accents ("réunion" does not find "reunion")
and stops at 1,000 results (the counter then shows "1000+"). On a very long or
damaged document it may fail: the message "Search failed in this document" then
appears.
