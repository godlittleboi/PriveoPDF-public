# Split PDF

## What it does

Create several PDFs from one document.

## How to use it

Add the PDF, then choose how to **SPLIT** in the right column:

- **Every N pages** (default, 2 pages per file): set the number of pages per
  file; the last file keeps the remaining pages;
- **One page per file**;
- **By groups (drag and drop)**: distribute pages visually between output
  groups;
- **By ranges**: type one range per file, for example `1-3,4-6`.

The PDF’s folder is proposed; **CHANGE…** lets you choose another one. The names
of the files to create appear before the action, for example
`Report_part-1.pdf`. Until the split is possible, the button stays greyed out
with the reason below it.

## Result

Each non-empty group becomes a new local PDF. The number of files created
appears below the button, with **OPEN FOLDER**. The source document remains
unchanged.

## Limits

Empty groups are ignored. A one-page document cannot be split, and a split that
would copy the whole document into a single file is refused. If a file with a
planned name already exists in the folder, the button stays greyed out: choose
another folder.
