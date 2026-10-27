# TofuAPI

A small web API for inspecting, previewing, subsetting, and rendering text with font files. Upload a TrueType font and get back its metadata, a preview image, a smaller font containing only the characters you need, or an image of your own text set in that font.

The name comes from "tofu", the nickname for the empty boxes (□) shown when a font has no glyph for a character.

<!-- TODO: add a screenshot or sample output, e.g. docs/images/render-example.png -->

## Features

| Endpoint | What it does                                                                               | Returns |
|---|--------------------------------------------------------------------------------------------|---|
| `POST /metadata` | Retrieves a font's names, style, license and embedding permissions, and character coverage | JSON |
| `POST /preview` | Draws a grid of sample characters from the font                                            | PNG image |
| `POST /subset` | Creates a smaller font that keeps only the glyphs needed for the text requested            | `.ttf` font file |
| `POST /render` | Draws the text requested in the font and settings requested                                | PNG image |

Uploaded fonts are processed in memory and are not stored by the app.

## Quick start

**Requirements:** Python 3.14 or newer, and [uv](https://docs.astral.sh/uv/).

```bash
git clone <your-repo-url>
cd TofuAPI
uv sync
uv run fastapi dev app/main.py
```

The API is now running at `http://127.0.0.1:8000`. 
Open `http://127.0.0.1:8000/docs` for interactive documentation where you can upload a font and try each endpoint.

## API reference

Every endpoint takes the font as a multipart form upload in a field named `file`. Other settings are query parameters.

### `POST /metadata`

Returns information read from the font's tables.

```bash
curl -X POST http://127.0.0.1:8000/metadata -F "file=@MyFont.ttf"
```

Response shape (the values here are illustrative):

```json
{
  "names": {
    "family": "My Font",
    "style": "Regular",
    "full_name": "My Font Regular",
    "version": "Version 1.000",
    "copyright": "..."
  },
  "style": {
    "weight": "Regular",
    "width": "Normal",
    "italic": false,
    "bold": false,
    "monospaced": false
  },
  "license": {
    "text": "...",
    "url": "...",
    "embedding": "installable",
    "no_subsetting": false
  },
  "coverage": {
    "num_glyphs": 1294,
    "num_codepoints": 938
  }
}
```

Fields the font does not provide come back as `null`. `embedding` is one of `installable`, `editable`, `preview_and_print`, or `restricted`.

### `POST /preview`

Returns a PNG grid of sample characters (A-Z, a-z, 0-9). Fonts with none of those characters show the first printable characters they do contain.

| Parameter | Default | Allowed |
|---|---|---|
| `size` | 48 | 12 to 128 (pixels) |

```bash
curl -X POST "http://127.0.0.1:8000/preview?size=64" -F "file=@MyFont.ttf" -o preview.png
```

### `POST /subset`

Returns a new, smaller `.ttf` containing only the glyphs for the characters in `text`. The response is a download named `subset.ttf`.

| Parameter | Default | Allowed |
|---|---|---|
| `text` | required | 1 to 64 characters |

```bash
curl -X POST "http://127.0.0.1:8000/subset?text=Hello" -F "file=@MyFont.ttf" -o subset.ttf
```

Characters the font does not support are left out. When that happens, the response includes an `Unsupported-Characters` header listing them as comma-separated Unicode code points, for example `U+65E5,U+672C`. If the font supports none of the requested characters, the request fails with a 422.

### `POST /render`

Returns a PNG of `text` set in the font. Text wraps at word boundaries to fit the image width, explicit line breaks are respected, and a single word wider than a line is broken across lines.

| Parameter | Default | Allowed |
|---|---|---|
| `text` | required | 1 to 1000 characters |
| `image_width` | 800 | 200 up to the configured maximum (pixels) |
| `font_size` | see `app/config.py` | 8 to 100 (pixels) |
| `font_color` | `#000000` | `#` followed by six hex digits |

```bash
curl -X POST "http://127.0.0.1:8000/render?text=Hello%20world&image_width=800&font_size=48&font_color=%23333333" \
  -F "file=@MyFont.ttf" -o render.png
```

If the finished image would be taller than the configured maximum, the request fails with a 422.

### Calling the API from a terminal

- On Windows PowerShell, use `curl.exe` (plain `curl` is an alias for another command) and put the whole command on one line.
- A `#` in a URL must be written as `%23`, otherwise the client cuts the URL off there. That is why the color above is `%23333333`.
- A line break in `text` is written as `%0A`, for example `text=First%20line%0ASecond%20line`. The `/docs` page cannot send a line break in a text box, so use curl or a test client for multi-line text.

### Errors

| Status | Meaning |
|---|---|
| 400 | The upload is not a font that can be read |
| 413 | The upload is larger than the size limit |
| 422 | A parameter is missing or out of range, the font's tables cannot be read, the font supports none of the requested characters, or the rendered image would be too tall |

Error responses are JSON with a `detail` field.

## Limits and configuration

Limits live in `app/config.py`: the maximum upload size (10 MB), and the maximum width and height of rendered images. Parameter ranges are listed in the API reference above.

## Project structure

```
app/
├── main.py              # creates the FastAPI app and registers the router
├── config.py            # size limits and defaults
├── utils.py             # shared helpers (upload reading, character support check)
├── routers/
│   └── fonts.py         # the four endpoints: HTTP handling and error mapping only
└── services/
    ├── font_loader.py   # opens an uploaded font and validates it
    ├── metadata.py      # reads names, style, license, coverage
    ├── preview.py       # chooses sample characters and draws the grid
    ├── subset.py        # subsetting with fontTools
    └── render.py        # line wrapping and drawing text
tests/
├── fixtures/            # test fonts (see "Testing")
├── helpers.py           # shared constants and functions to damage fonts for tests
├── conftest.py          # font fixtures
└── test_*.py
```

The routers deal only with HTTP (reading the upload, status codes, response headers). The services contain the font and image work and know nothing about the web framework, so they can be tested directly.

Built with [FastAPI](https://fastapi.tiangolo.com/), [fontTools](https://github.com/fonttools/fonttools) (reading and subsetting fonts), and [Pillow](https://python-pillow.org/) (drawing text).

## Testing

The tests require font fixture files, which are not included in this repository.
Before running the test suites, 
1. Create the `tests/fixtures/` folder if it does not already exist.
2. Download or provide the required font files and store them in the folder. 
   See `conftest.py` for the naming and font files needed.

To run:

```bash
uv run pytest
```

The tests cover the service functions directly and the endpoints through FastAPI's test client. They use real fonts stored in `tests/fixtures/`, plus fonts generated during the test run (for example a font with no Latin characters, made by subsetting a normal one) and deliberately damaged copies (a table overwritten or removed) to check that bad fonts return an error and never crash the server.


## Known limitations

- Text is laid out left to right. Right-to-left and complex scripts (such as Arabic or Devanagari) are not shaped correctly.
- Layout uses Pillow's basic text measuring, so kerning and ligatures may differ slightly from how a browser would draw the same text.
- Long words are broken by character count, not at syllables.
- Breaks use Unicode code points, so a letter and its combining accent can be separated.
- In `/render`, characters the font lacks are drawn with the font's own "missing character" shape, which differs between fonts (a box in some, blank in others).
- In `/render`, tabs are treated and rendered as a single space character.
- Developed and tested with TrueType (`.ttf`) files. Font collections (`.ttc`) and web font formats are not supported.

## Future Improvements

- Optional PDF and SVG output for `/render`
- Hyphenation by syllable for English text, following the Chicago Manual of Style guidelines
- Partial results with warnings for fonts with a damaged table
- Support for complex scripts through a text shaping engine


## License

<!-- TODO: choose a license for this project and add a LICENSE file -->