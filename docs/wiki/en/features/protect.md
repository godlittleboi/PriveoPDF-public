# Protect PDF

## What it does

Add a password required to open the PDF.

## How to use it

Open **Protect PDF** from the home screen or **Tools**. Choose a PDF, enter a
new password and confirm it. Use a long passphrase and keep it: PriveoPDF cannot
recover it. A copy `<name>_protected.pdf` is proposed in the PDF's folder
(**CHANGE…** for another destination); then click **PROTECT PDF**.
You can cancel while processing. **Show/Hide** next to each field lets you check
what you are typing.

To keep a single file, select **Replace this PDF**. The box is cleared for each
new PDF and when leaving the tool.
Confirm when starting: after success, the name stays the same and the previous
version is not kept. An error or cancellation before saving leaves it intact.

## Result

The PDF uses AES-256 encryption. The result appears below the button.
**OPEN PDF** opens its protected state in
PriveoPDF with an **Unlock PDF** button. To read its pages while keeping the
protection, open it in your usual PDF reader.
By default a copy is created and the original stays unchanged. Only selecting
**Replace this PDF** and confirming allows the original to be replaced.

## Limits

The masked password fields are cleared after starting or leaving the tool.
The password is not saved in preferences or logs. It travels only in memory
during processing; immediate physical erasure of all memory copies is not guaranteed.
The limit is 127 UTF-8 bytes (accented characters may use several bytes), with
no null character or line break. Spaces are not trimmed.
Already encrypted PDFs, digitally signed documents and documents whose integrity
cannot be verified are refused. Unlock a copy first to change its password.
Printing and copying restrictions are not offered here. Encryption does not
remove metadata or guarantee PDF/A compliance.
