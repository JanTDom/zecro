---
name: newspaper-vision-segmentation
description: >-
  Advanced computer vision, photo cutout segmentation (szparowanie), alpha mask extraction, contour polygon vectorization, visual saliency mapping, and gaze direction orientation for editorial newspaper layouts. Use this skill when processing raw photographs into background-free knockout silhouettes (pakszot), generating SVG/CSS clip-paths, computing text wrap margins (shape-outside), and positioning portraits so subjects face inward toward reading columns.
---

# Newspaper Vision & Cutout Segmentation Skill

In editorial design, knockout silhouettes (**pakszoty / cutouts**) give energy and dynamism to a page. This skill details the automated pipeline from raster image to vector wrap contour.

## 1. The 5-Step Cutout Pipeline

```text
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  RAW PHOTO   │ ──▶ │ SEGMENTATION │ ──▶ │ CONTOUR POLY │
│  (JPG/PNG)   │     │ (Alpha Mask) │     │ (Vector SVG) │
└──────────────┘     └──────────────┘     └──────────────┘
                                                 │
                                                 ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  IN-DESIGN   │ ◀── │ OFFSET DILATE│ ──▶ │   CSS WRAP   │
│ (TextWrap)   │     │ (3mm margin) │     │(shape-outside)
└──────────────┘     └──────────────┘     └──────────────┘
```

1. **Background Removal**: Neural segmentation (e.g. RMBG / U2-Net) generates a high-contrast alpha channel ($A \in [0, 255]$).
2. **Contour Extraction**: Tracing boundary pixels where $A \ge 128$.
3. **Polygon Simplification**: The **Ramer-Douglas-Peucker (RDP)** algorithm reduces thousands of pixel vertices down to 12–30 key vector points ($\epsilon = 0.015$).
4. **Padding & Offset Dilation**: Expanding the polygon outwards by `offset_mm` (typically 3.0mm – 4.5mm) to create a clean margin between the photo silhouette and surrounding justified body copy.
5. **Format Generation**:
   - **CSS**: `shape-outside: polygon(...)` + `clip-path: polygon(...)`
   - **IDML**: `TextWrapPreference` with `Contour` path coordinates.

## 2. Gaze Direction & Saliency Rule

**The Golden Editorial Gaze Rule**:
- Any portrait or person photographed MUST face **inwards toward the text column**, guiding the reader's eye into the journalism.
- A photo where the subject looks outward (off the page edge) is a critical layout error that drains visual energy.
- When placing a photo in the right-hand column, the subject must face left. In a left-hand column, the subject must face right.

## References & Scripts
- [Contour & Saliency Pipeline](../../../backend/app/engine/image_ops.py)
