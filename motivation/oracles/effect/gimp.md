<!-- DRAFT 2026-10-20 (ChuangMa side, claude-opus-5.5): to be reviewed by the researchers before any formal run.
     General state -> operation -> visual-effect principles for GIMP 2.10. No task-specific operations or values.
     Written without looking at any agent trajectory. -->

# How GIMP 2.10 operations change the image, depending on its current state

## Where an operation applies
- Colour adjustments, filters, fills and erasing act only on the **active layer** (or layer mask, if the mask is the
  active target), and only **inside the current selection** if one exists. With no selection they act on the whole
  active layer. Another layer above can hide the result in the composite.
- A selection with a feathered or antialiased edge produces a gradual transition; a hard selection produces a hard
  edge. A floating selection must be anchored or turned into a layer before most operations apply to the image.
- Zoom level, rulers, guides and the grid change the view only, never the pixels.

## Tone and exposure
- The visible result of a tonal tool depends on the image's current histogram. Raising brightness lifts all tones
  equally; on an already bright image it quickly clips highlights to white and loses detail. Increasing contrast
  spreads tones away from the middle; on a low-contrast (flat) image it adds punch, on a contrasty image it clips
  both ends.
- Levels maps an input black point / white point / gamma to the output range: moving the input white point down to
  where the histogram's data actually ends brightens an underexposed image without clipping detail; moving it past
  the data clips. Gamma (the middle input value) brightens or darkens mid-tones while keeping black and white fixed.
- Curves does the same per tone: lifting the lower part of the curve opens shadows, an S-shaped curve increases
  mid-tone contrast. Per-channel curves or levels shift colour balance.
- Exposure scales light linearly (like camera stops); Shadows-Highlights lifts dark regions and recovers bright ones
  locally, keeping overall contrast more natural than a global brightness change.
- Automatic tools (Stretch Contrast, Normalize, Equalize, White Balance) compute their result from the current
  pixel statistics, so the same command gives a strong change on a flat or colour-cast image and almost none on an
  image that already spans the full range. Equalize flattens the histogram and can look harsh.

## Colour
- Hue-Saturation rotates hues around the colour wheel (a fixed hue offset changes every colour by the same angle)
  and scales saturation; already grey pixels stay grey whatever the hue shift. Saturation changes affect vivid
  colours most.
- Color Balance and Color Temperature shift the balance between complementary colours; correcting a colour cast
  means moving towards the complement of the cast (e.g. a blue cast needs warming).
- Desaturate keeps the image in RGB mode with grey pixels; Image > Mode > Grayscale changes the image mode so it
  can only hold grey values afterwards. Colorize first removes colour, then tints with one hue, which is how sepia
  or monochrome tints arise.
- Invert maps each channel value v to 255 - v; applying it twice restores the original. Threshold maps each pixel
  to black or white by comparing its value with the threshold, so the result depends strongly on the image's
  brightness distribution. Posterize reduces the number of levels per channel and creates flat colour bands.

## Layers, blend modes and opacity
- A layer's visible effect depends on what lies beneath it. Blend modes combine the layer (blend colour) with the
  composite below (base colour): Multiply always darkens or keeps (white is neutral), Screen always lightens or
  keeps (black is neutral), Overlay/Soft light increase contrast depending on whether the base is lighter or darker
  than middle grey, Difference shows where the layers differ. Opacity mixes the blended result with the unchanged
  base, so lower opacity weakens any mode.
- Layer order matters: moving a layer up or down changes what it covers and what its blend mode acts on. Merge Down
  combines a layer with the one directly below using the upper layer's mode and opacity; Flatten removes all
  transparency by compositing onto the background colour.
- A layer mask hides (black) or shows (white) its layer without deleting pixels; grey shows it partly. Painting on
  the mask therefore changes visibility, while painting on the layer changes colour.
- A layer can be smaller or larger than the canvas; pixels outside the canvas are not shown or exported, and areas of
  the canvas not covered by any layer are transparent (or show the checkerboard).

## Transparency
- Without an alpha channel, erasing, cutting or Clear fill with the background colour instead of transparency;
  after Layer > Transparency > Add Alpha Channel the same operations produce transparent pixels. Color to Alpha
  turns the chosen colour transparent and makes similar colours semi-transparent.
- File formats decide what survives export: JPEG has no transparency (transparent areas become a solid colour) and
  lossy compression; PNG keeps transparency and exact pixel values.

## Selections
- Fuzzy Select and Select by Color include pixels whose colour is within the threshold of the clicked colour: a low
  threshold selects too little on gradients or noisy backgrounds, a high one leaks into the subject. Fuzzy Select
  takes only connected pixels; Select by Color takes them anywhere in the layer.
- Feathering blurs the selection edge by the given radius; Grow/Shrink move it outward/inward; Invert swaps inside
  and outside, which is how one edits the background instead of the subject.

## Filters
- The visual strength of a filter depends on image size: the same blur radius or noise amount is strong on a small
  image and subtle on a large one. Previews in filter dialogs show the effect on the current state before applying.
- Gaussian blur softens everything; motion blur smears in one direction; Unsharp Mask increases local contrast at
  edges (radius = width of the halo, amount = strength, threshold = minimum edge contrast affected), and too much of
  it creates bright and dark halos. Noise filters add random variation per pixel (RGB noise can change colour,
  HSV/value noise mostly brightness). Despeckle/median-type filters remove isolated outliers but soften fine detail.
- Edge-detect and emboss-type filters replace the image by a map of its edges or relief, so most of the original
  colour disappears. Artistic and distortion filters (cartoon, oilify, cubism, ripple, wind, newsprint, pixelize)
  restructure the image and are hard to undo except with Undo.
- Decorative scripts (borders, shadows, rounded corners) may enlarge the canvas, add layers or flatten the image,
  depending on their options.

## Geometry
- Scale Image resamples every layer and changes the pixel dimensions; Canvas Size changes only the drawable area
  (new areas are empty or filled, existing pixels keep their size) and the offset decides where the old content
  sits; Print Size changes only the resolution metadata (pixels per inch), not the pixels.
- Crop removes everything outside the crop rectangle. Rotating by an arbitrary angle leaves empty corners unless the
  result is clipped or cropped. Flip mirrors (horizontal flip swaps left and right); rotating by 180 degrees is not
  the same as a single flip. Offset shifts content, and with wrap-around the part pushed out re-enters on the other
  side.

## Undo and saving
- Every applied operation is cumulative: applying a tonal or filter operation twice doubles its effect. Undo
  (Ctrl+Z) restores the previous state exactly. Export writes a file of the current composite; it does not change
  the open image, and Save (.xcf) keeps layers while exports to JPEG or PNG flatten them.
