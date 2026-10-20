<!-- DRAFT 2026-10-20 (ChuangMa side, claude-opus-5.5): UNVERIFIED against the live GIMP 2.10.36 in the benchmark VM;
     to be checked on screenshots and reviewed by the researchers before any formal run.
     Where controls are in GIMP 2.10. Locations only: it does not say which tool or which values solve a task. -->

# Where things are in GIMP 2.10

## Window layout (single-window mode, default theme)
- The menu bar is at the top of the GIMP window: File, Edit, Select, View, Image, Layer, Colors, Tools, Filters,
  Windows, Help. The image canvas is in the middle.
- The toolbox is on the left; the options of the active tool appear in the Tool Options dock below or beside it.
  Tools are grouped: hovering shows their name, right-clicking or long-pressing a group shows the other tools in it.
- The Layers, Channels, Paths and Undo History docks are on the right. The Layers dock lists layers top to bottom;
  its bottom row has buttons for new layer, raise, lower, duplicate, anchor, mask and delete. The mode (blend mode)
  drop-down and the Opacity slider are at the top of the Layers dock.
- Dialogs of colour tools and filters open as separate windows with a preview check box and, at the bottom right,
  Reset / OK / Cancel buttons. Sliders accept typed values: click into the number field, select it and type.

## Menus (main entries)
- **File**: New, Open, Open as Layers, Open Recent, Save, Save As, Save a Copy, Revert, Export To, Overwrite,
  Export As (Shift+Ctrl+E), Print, Close View, Quit. Export As opens a file dialog with a name field at the top, a
  folder list, a "Select File Type (By Extension)" expander at the bottom, then an options dialog for the format.
- **Edit**: Undo, Redo, Undo History, Cut, Copy, Copy Visible, Paste, Paste In Place, Paste Into Selection, Paste as
  (New Layer, New Image, ...), Clear, Fill with FG Color, Fill with BG Color, Fill with Pattern, Stroke Selection,
  Stroke Path, Preferences, Keyboard Shortcuts.
- **Select**: All, None, Invert, Float, By Color, From Path, Feather, Sharpen, Shrink, Grow, Border, Remove Holes,
  Rounded Rectangle, Toggle Quick Mask, Save to Channel, To Path.
- **View**: zoom levels, Show Grid, Show Guides, Snap options, Fullscreen.
- **Image**: Duplicate, Mode (RGB, Grayscale, Indexed), Precision, Color Management, Transform (Flip Horizontally,
  Flip Vertically, Rotate 90 clockwise, Rotate 90 counter-clockwise, Rotate 180, Arbitrary Rotation, Guillotine),
  Canvas Size, Fit Canvas to Layers, Fit Canvas to Selection, Print Size, Scale Image, Crop to Selection, Crop to
  Content, Zealous Crop, Merge Visible Layers, Flatten Image, Guides, Configure Grid, Image Properties, Metadata.
- **Layer**: New Layer, New from Visible, New Layer Group, Duplicate Layer, Anchor Layer, Merge Down, Delete Layer,
  Stack (raise, lower, to top, to bottom, reverse order), Mask (Add Layer Mask, Apply, Delete, Show, Edit, Disable,
  Mask to Selection), Transparency (Add Alpha Channel, Remove Alpha Channel, Color to Alpha, Semi-Flatten, Threshold
  Alpha, Alpha to Selection), Transform (Flip, Rotate, Arbitrary Rotation, Offset Shift+Ctrl+O), Layer Boundary
  Size, Layer to Image Size, Scale Layer, Crop to Selection, Crop to Content.
- **Colors**: Color Balance, Color Temperature, Hue-Chroma, Hue-Saturation, Saturation, Exposure,
  Shadows-Highlights, Brightness-Contrast, Levels, Curves, Invert, Linear Invert, Value Invert, Auto (Equalize,
  White Balance, Stretch Contrast, Stretch Contrast HSV, Color Enhance, Normalize), Components, Desaturate (Color to
  Gray, Desaturate, Mono Mixer, Sepia), Map, Tone Mapping, Info (Histogram), Threshold, Colorize, Posterize, Color to
  Alpha, Dither.
- **Tools**: the same tools as the toolbox, grouped as Selection Tools, Paint Tools, Transform Tools, Color Tools,
  plus Text, Paths, Color Picker, Measure, Zoom, GEGL Operation.
- **Filters**: Repeat Last, Re-Show Last, Reset All Filters, Blur, Enhance (including Sharpen (Unsharp Mask), Noise
  Reduction, Despeckle, Red Eye Removal), Distorts (including Emboss, Engrave, Mosaic, Newsprint, Ripple, Waves,
  Whirl and Pinch, Wind, Lens Distortion), Light and Shadow (including Drop Shadow, Long Shadow, Vignette, Lens Flare,
  Supernova, Lighting Effects), Noise (CIE lch, HSV, Hurl, Pick, RGB Noise, Slur, Spread), Edge-Detect (Difference of
  Gaussians, Edge, Laplace, Neon, Sobel), Generic (Convolution Matrix, Dilate, Erode, Distance Map), Combine,
  Artistic (including Cartoon, Cubism, Oilify, Photocopy, Softglow, Apply Canvas, Glass Tile), Decor (including Add
  Bevel, Add Border, Fog, Fuzzy Border, Old Photo, Round Corners), Map (including Bump Map, Displace, Tile Seamless,
  Paper Tile), Render (Noise: Cell, Perlin, Plasma, Simplex, Solid Noise; Pattern: Checkerboard, Grid, Maze, Sinus,
  Spyrograph; Lens Flare), Web, Animation, Python-Fu, Script-Fu.

## Toolbox shortcuts (default)
Rectangle Select R, Ellipse Select E, Free Select F, Fuzzy Select U, Select by Color Shift+O, Scissors I, Foreground
Select; Move M, Alignment Q, Crop Shift+C, Unified Transform Shift+T, Rotate Shift+R, Scale Shift+S, Shear Shift+H,
Perspective Shift+P, Flip Shift+F, Cage Shift+G, Warp W; Text T, Bucket Fill Shift+B, Gradient G, Pencil N,
Paintbrush P, Eraser Shift+E, Airbrush A, Ink K, Clone C, Heal H, Smudge S, Dodge/Burn Shift+D; Color Picker O,
Measure Shift+M, Zoom Z. Foreground/background colour swatches are below the tools (X swaps them, D resets to
black/white); clicking a swatch opens the colour dialog with an HTML-notation field.
