# vibecleaner

**A Windows desktop app that finds dialogue in manga images, translates it, removes the original text, and places the translation back into the artwork.**

[한국어](README.md) · [English](README.en.md)

> This project is under active development. Keep a separate copy of important source images and review the result before exporting it.

## Why use it?

Translating a comic image usually means finding every speech bubble, reading the text, translating it, cleaning the original lettering, and typesetting the translation. vibecleaner connects those jobs in one workspace.

You can let the app create a first pass, compare it with the original, and correct individual bubbles in the inspector when needed.

## What makes it useful?

- **One continuous workflow:** detection, OCR, translation, text removal, and typesetting.
- **Designed for comics:** supports vertical and diagonal dialogue as well as multi-bubble pages.
- **Quick comparison:** hold the Compare button to view the original page.
- **Multi-page projects:** add, select, translate, save, and export several pages together.
- **Local image processing:** detection, OCR, and inpainting run on your computer.
- **Flexible translation:** use a convenient online provider or a local environment such as Ollama.

## Getting started

### 1. Install the app

If a Windows build is available, download it from [GitHub Releases](https://github.com/gapfixnid/vibecleaner/releases).

To run the source code instead, follow the [development and build guide](docs/development-guide.md). Building from source requires Node.js, Python, and Rust, so a packaged release is easier for most users.

### 2. Complete initial setup

- **Source language:** the language written in the image.
- **Target language:** the language you want to produce.
- **Processing profile:** choose `Balanced` if you are unsure.
- **Translation provider:** Google Translate is a simple online starting point. Choose Ollama for a fully local translation setup.

The app checks for the local models required by your choices. The first run may take longer while those files download.

### 3. Add images

Select **Add Images** on the empty screen and choose one or more comic pages. PNG, JPG/JPEG, WebP, and BMP inputs are supported.

When you add multiple images, the page panel lets you manage them as one project.

### 4. Translate and review

Select **Translate** in the floating bar below the canvas. The app runs:

`region detection → OCR → translation → original-text removal → translated-text layout`

After processing:

- Hold **Compare** to see the original image.
- Use the **page panel** to select and manage pages.
- Use the **inspector** to edit a bubble's source text, translation, and layout.
- Use the arrows at the upper canvas edges to collapse or reopen the side panels.

### 5. Save or export

- Select the app icon at the upper left and choose **Save Project** to continue editing later.
- Use the save button in the page panel to export selected result images.
- Select several pages to translate or export them together.

Saving a project preserves editable work. Exporting creates finished image files.

## Recommended settings

The defaults are the safest place to start.

| Goal | Recommended option |
| --- | --- |
| Not sure what to choose | Balanced profile |
| Best Japanese manga OCR | Manga OCR |
| Other languages or faster OCR | PP-OCR |
| Better text removal | LaMa inpainting |
| Fast preview | OpenCV inpainting |

Only adjust advanced padding, mask dilation, and confidence settings when a particular page needs correction.

## Common questions

### Why is the first translation slow?

The app may need to download and load a local model. Later operations in the same session are usually faster.

### Vertical or diagonal text is read incorrectly

Set the source language to Japanese and try Manga OCR or the Balanced profile. You can also correct the recognized source text in the inspector before translating again.

### Inpainting blurs outside a speech bubble

Use LaMa inpainting and enable clipping to the speech-bubble boundary. If detection is wrong, enable the detection overlay in Advanced Settings and inspect the region first.

### The translated text is positioned poorly

Adjust alignment, font size, and line spacing in the inspector. Automatic layout can vary with bubble shape and translation length.

### Are my images uploaded?

Detection, OCR, and inpainting run locally. Online translation providers receive the text required for translation. An image can also be sent if you explicitly enable image context for a provider that supports it. Use Ollama with a local model if you do not want translation data sent to an external service.

## Documentation

- [한국어 사용자 안내](README.md)
- [Development and build guide](docs/development-guide.md)
- [개발 및 빌드 가이드](docs/development-guide.ko.md)
- [Backend dependency contract](docs/backend-dependency-contract.md)
- [Pipeline architecture decision](docs/adr/0001-evolve-the-pipeline-core-without-a-full-rewrite.md)
- [Provider extension contract](docs/provider-extension-contract.md)
- [Schema versioning policy](docs/schema-versioning-policy.md)

## License and acknowledgements

This repository is licensed under the [Apache License 2.0](LICENSE). Downloaded models, bundled fonts, and external services retain their own licenses and terms. See [NOTICE](NOTICE) for attribution details.

Please report problems or suggestions through [GitHub Issues](https://github.com/gapfixnid/vibecleaner/issues).
