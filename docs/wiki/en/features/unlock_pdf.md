# Unlock PDF

## What it does

Remove encryption from a PDF whose password you know.

## How to use it

Open **Unlock PDF** from the home screen or **Tools**. Opening a protected PDF
in the viewer shows a message and an **Unlock PDF** button leading directly to
this tool. Drop the protected PDF
directly into this tool; no preview is needed. Enter the known password. A copy
`<name>_unlocked.pdf` is proposed (**CHANGE…** for another destination); then
click **UNLOCK PDF**. You can cancel while processing.
An incorrect password is refused: enter it again to retry.
Use **Show/Hide** to check your input.

From another tool, **UNLOCK PDF**, shown below a protected PDF, opens this tool
directly on that file. A PDF that is not protected is reported as soon as it is
loaded (“This PDF is not protected: nothing to unlock.”): no password is
requested.

To keep a single file, select **Replace this PDF**, then confirm when starting.
The file keeps its name and becomes readable without a password; the previous
protected version is not kept. An error or cancellation before saving keeps
the previous file intact.

## Result

The result appears below the button. **OPEN PDF** opens the PDF without a
password. Compare its pages with the
original. By default, a copy is created and the protected original stays unchanged.
Only confirmed replacement changes the current file. Anyone with the result can
read its contents.

## Limits

This tool does not search for or recover lost passwords. Unencrypted PDFs,
digitally signed documents and documents whose integrity cannot be verified
produce no output.
The password stays in memory during processing, with no preference, secret
file or log. Fields are cleared after starting or leaving the tool; physical
erasure of every memory copy is not guaranteed.
The limit is 127 UTF-8 bytes, with no null character or line break.
Metadata and PDF content are preserved, with no automatic cleaning.
