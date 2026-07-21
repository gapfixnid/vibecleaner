# vibecleaner model selection and custom ONNX guide

[한국어](model-guide.ko.md) · [English](model-guide.md) · [Back to the user guide](../README.en.md)

This guide explains the built-in choices and how to add ONNX files you prepared yourself. If you are new to the app, keep the options marked `Recommended` in initial setup or Settings.

## Recommended defaults

| Stage | Recommended model | Purpose |
| --- | --- | --- |
| Detection | RT-DETR-v2 FP32 | Find speech bubbles and dialogue regions |
| OCR | PP-OCRv6 Medium ONNX | Recognize text, including Japanese |
| Inpainting | AOT ONNX | Reconstruct areas where source text was removed |

When a selected model is missing, the app checks and downloads the required files while saving setup. Models live under `%LOCALAPPDATA%\vibecleaner\models`, outside the installation directory.

## Available model families

### Detection

- **RT-DETR-v2 FP32 (recommended):** the default choice when accuracy is the priority.
- **RT-DETR-v2 INT8:** reduces download and runtime cost.
- **YOLOv8/11 ONNX:** supports compatible YOLO-family exports.

### OCR

- **PP-OCRv6 Medium ONNX (recommended):** intended for typical comic pages and vertical or diagonal dialogue.
- **PP-OCRv6 Small ONNX:** uses fewer resources.

OCR uses a PP-OCR DB Detection and CTC Recognition pair. It does not send images or low-confidence crops to an external Vision service for OCR fallback.

### Inpainting

- **AOT ONNX (recommended):** a balanced default for ordinary speech bubbles and lettering removal.
- **LaMa ONNX:** worth comparing for large areas or repeating textures.

If cleanup spreads beyond a bubble, enable bubble-boundary clipping and inspect the detection overlay before increasing mask values.

## Add custom ONNX files

Close the app, copy files into this layout, then restart the app or reopen Settings:

```text
%LOCALAPPDATA%\vibecleaner\models\
├─ detection\
├─ ocr\
│  └─ my-ocr-model\
└─ inpainting\
```

### Detection models

Place an ONNX file under `detection`. Its filename must contain a supported family name:

- RT-DETR-v2: `rtdetr` or `rt-detr`
- YOLOv8/11: `yolo`

YOLO output classes must use `0=speech bubble` and `1+=text`. An RT-DETR-v2 model must be compatible with the labels, boxes, and scores output layout expected by the app.

### OCR models

Create one subdirectory under `ocr` containing all of the following:

- a PP-OCR DB Detection ONNX file with `det` in its filename;
- a PP-OCR CTC Recognition ONNX file with `rec` in its filename; and
- a `.yml` or `.yaml` file containing preprocessing and character-dictionary metadata.

The app lists the directory as one OCR model only when all three parts are present together.

### Inpainting models

Place an ONNX file under `inpainting`. Its filename must contain `aot` or `lama`. A file can be discovered by name but still fail at runtime when its input and output tensors are incompatible with the corresponding app runner.

## If a model does not appear

1. Confirm that the file extension is `.onnx`.
2. Confirm that the filename contains a supported family name.
3. For OCR, keep the det, rec, and YAML files in one subdirectory.
4. Close and reopen Settings to rescan the model directory.
5. Check the app log for discovery or ONNX Runtime errors.

A recognized filename does not guarantee model quality or complete compatibility. Keep your source images and validate a small set of pages first.
