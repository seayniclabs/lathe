---
name: pdf-forms
description: Make a PDF with real fillable fields (text boxes and checkboxes that a reader can tick or type in) from a page layout, for planners, trackers, checklists and order forms. Use when the user needs a PDF that people fill in on screen, not a static printable. Lathe's pdf tools read and split fields but do not create them.
license: MIT
source: https://github.com/seayniclabs/lathe
author: Seaynic Labs
---

# Fillable PDF forms

A fillable PDF needs two things: a page that looks right, and a form layer on top of it. Browsers print the page, but a browser print has no form fields. A PDF library can add form fields, but it cannot lay out a page. So the work is two steps: render the page, record where each field sits, then add the fields at those spots.

## Steps

1. Design the page in HTML and CSS. Give every fillable element a unique `data-field="<name>"` attribute and a `data-type` of `text` or `checkbox`. Use a fixed page size: US Letter is 8.5 x 11 inches, which is 816 x 1056 CSS pixels at 96 pixels per inch.
2. Render the page with Playwright and Chromium (`pip install playwright`, then `playwright install chromium`). Call `page.pdf()` to write the visual layer, and call `page.evaluate()` to read each `[data-field]` element's `getBoundingClientRect()`. Save the rectangles to a JSON file. Take the rectangles from the live page. Do not compute them from the CSS.
3. Convert each rectangle to PDF points. A PDF point is 1/72 inch, so multiply CSS pixels by 0.75. PDF coordinates start at the bottom-left corner, so set `y_bottom = page_height_pt - css_bottom * 0.75`, and `y_top = page_height_pt - css_top * 0.75`.
4. Add a widget annotation for each field with pypdf. The snippet below does it for one page.
5. Write the file, then check it with the verification snippet below before you deliver it.

```python
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (ArrayObject, BooleanObject, DictionaryObject, FloatObject, NameObject,
                           NumberObject, TextStringObject)


def add_field(writer, page, name, kind, rect):
    """kind is 'text' or 'checkbox'. rect is [x1, y1, x2, y2] in PDF points, origin bottom-left."""
    annot = DictionaryObject({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Widget"),
        NameObject("/Rect"): ArrayObject([FloatObject(v) for v in rect]),
        NameObject("/T"): TextStringObject(name),
        NameObject("/F"): NumberObject(4),
        NameObject("/P"): page.indirect_reference,
    })
    if kind == "text":
        annot[NameObject("/FT")] = NameObject("/Tx")
        annot[NameObject("/V")] = TextStringObject("")
    else:
        annot[NameObject("/FT")] = NameObject("/Btn")
        annot[NameObject("/V")] = NameObject("/Off")
        annot[NameObject("/AS")] = NameObject("/Off")
    ref = writer._add_object(annot)
    if "/Annots" not in page:
        page[NameObject("/Annots")] = ArrayObject()
    page["/Annots"].append(ref)
    return ref


def build_form(layout_pdf, fields_json, out_pdf):
    """layout_pdf: the rendered page. fields_json: [{"name", "type", "rect"}, ...] in PDF points."""
    import json

    with open(fields_json) as fh:
        fields = json.load(fh)
    reader = PdfReader(layout_pdf)
    writer = PdfWriter(clone_from=reader)
    page = writer.pages[0]
    refs = ArrayObject()
    for f in fields:
        refs.append(add_field(writer, page, f["name"], f["type"], f["rect"]))
    writer._root_object[NameObject("/AcroForm")] = DictionaryObject({
        NameObject("/Fields"): refs,
        NameObject("/NeedAppearances"): BooleanObject(True),
    })
    writer.write(out_pdf)
```

Run `build_form` on the rendered page and the JSON from step 2 after converting the coordinates. It handles one page. For a multi-page form, pass each page to `add_field` with its own list.

## Verify before delivery

Check the structure, then look at a rendered page:

```python
from pypdf import PdfReader

fields = PdfReader("form.pdf").get_fields() or {}
assert fields, "no fillable fields: the file was flattened to plain ink"
kinds = {name: f.get("/FT") for name, f in fields.items()}
print(len(fields), "fields", kinds)
```

`/Tx` is a text field and `/Btn` is a checkbox. Assert each field's type against the list you built, and assert the count. Then render one page to PNG at 150 DPI and open it. A structural check cannot show a wrong font or a field in the wrong place.

## Gotchas

- Add the fields to the file you ship. A re-render that skips the form step ships the old file while the new layout looks correct in a preview. Run the form step as the last step of every build.
- Give checkboxes a `checkbox` type in the JSON, not a name that suggests one. A field named `*_checkbox` that holds `/Tx` looks like a box and types like a text field.
- A font referenced by a `file://` URL that does not exist fails silently. Check that each `@font-face` file is on disk, and check the rendered title in a PDF viewer.
- Keep the field names unique across the whole file.
