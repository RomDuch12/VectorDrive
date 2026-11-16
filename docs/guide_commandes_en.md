# Command guide — VectorDrive 0.921.0

Generated from the ribbon (outils/guide.py): every row is a real command.

## File

### Document

| Command | Shortcut | Purpose |
|---|---|---|
| New | Ctrl+N | New drawing, in a new tab |
| Open | Ctrl+O, Ctrl+Shift+O |  |
| Save | Ctrl+S |  |
| Save as | Ctrl+Shift+S |  |
| New from a template… |  | New drawing from a template (plate, title block, marks…) |
| Save as template… |  | Keep this drawing as a starting point for other drawings |
| Information |  | Title, author, client and comments of the document (kept in the file), and its figures: layers, objects, time spent |
| File previews |  | Preview of the chosen file in Recent and Open — for this session only (off by default: faster) |
| Quit |  | Close VectorDrive |

### Import / export

| Command | Shortcut | Purpose |
|---|---|---|
| Explorer menu |  | “Convert with VectorDrive ▸ to DXF, SVG, PDF, EPS, Batch processing…” on the right-click menu of drawings and folders in Windows Explorer (your account only) |
| Thumbnails in Explorer |  | Thumbnails of drawings (VND, DXF, SMB, SVG, AI, EPS, VDZ, PDF) and machine programs (G-code, SimPL…) in Windows Explorer, drawn by VectorDrive (your account only) |
| Import | Ctrl+I |  |
| Export | Ctrl+E |  |
| PDF proof | Ctrl+Shift+P | PDF proof for customer approval |
| Print | Ctrl+P | The selection, the plate, some layers or the whole drawing — on a sheet from A6 to A1, fitted at the advised scale, at 1:1 or at the chosen zoom; or as a PDF at actual size; or the proof page |
| Print the selection… |  | Print the selected objects alone: at 1:1 scale, or fitted to an A4 sheet with 15 mm margins |
| Assembly stock… |  | The piece of material of the selected object or group, drawn and dimensioned separately on the proof: neither engraved, machined nor exported. Several objects selected: they are grouped |
| Batch processing… |  | Convert drawings or whole folders at once (VND to DXF, PDF, SVG…), proofs optional |
| Export as STL… |  | The chosen reliefs (on a base) and the chosen closed shapes (extruded) as STL: 3D printing, other CAM software |

### Compare

| Command | Shortcut | Purpose |
|---|---|---|
| Compare |  | Compare the drawing with another one (open tab or file): added in green, removed in red, changed in orange |
| Next difference |  | Show the next area holding differences |
| Previous difference |  | Show the previous area holding differences |
| Close the comparison |  | Clear the comparison colours |

## Edit

### Action

| Command | Shortcut | Purpose |
|---|---|---|
| Undo | Ctrl+Z |  |
| Redo | Ctrl+A |  |
| Undo several… |  | List of changes: undo back to the chosen one |
| Redo several… |  | List of undone changes: redo up to the chosen one |
| Clear history |  | Forget the undo steps (frees memory on a large drawing) |

### Clipboard

| Command | Shortcut | Purpose |
|---|---|---|
| Paste | Ctrl+V, Shift+Ins |  |
| Cut | Ctrl+X, Shift+Del |  |
| Copy | Ctrl+C, Ctrl+Ins |  |
| Delete | Del |  |
| Bring back erased |  | What the last Erase removed comes back, each object in its place, even after other changes (one undo step) |
| Match properties |  | The properties of the first selected object go to the others (only one: to the objects clicked next): tool, fill, layer, text formatting (choice in F10 › Drawing) |
| Fill / empty |  | Fills the closed contours of the selection, or empties them if they already are (groups included). A filled import is emptied this way, and vice versa |
| Colour… |  | Gives a colour to the selected objects: their stroke, and their fill when filled. It does not depend on the tool; Ctrl+8 shows or hides the colours |
| Tool colour |  | Removes the colour given to the selected objects: they take their tool colour again |

### Selection

| Command | Shortcut | Purpose |
|---|---|---|
| Selection | Esc |  |
| All | Ctrl+L | Select all |
| Invert |  | Invert selection |
| Filter | F9 | Selection filter: only the chosen kinds of objects can be selected |
| Preview | F4 | Preview while moving, resizing and rotating: whole objects (otherwise only their box, faster) |
| Modes |  | Selection modes: add, deselect, keep; sorting of the selection (machining order) |
| Lasso |  | Lasso selection: clicks = polygonal lasso, drag = freehand; double-click or Enter takes the objects touched (selection operator and filter included) |
| Same tool |  | Select all objects with the same tool as the selection |
| Same shape |  | Select all objects of the same kind and size as the selection |
| Freeze |  | Freeze the selection: it stays visible but can no longer be changed. A click points at a frozen object, this button unfreezes it |
| Unfreeze all |  | Unlock all objects |
| Hide |  | Hide the selection |
| Show all |  | Show hidden objects again |
| Isolate |  | Show only the selection (the other objects hidden); “End isolation” shows them again |
| End isolation |  | Show again the objects hidden by “Isolate” |

### Order

| Command | Shortcut | Purpose |
|---|---|---|
| Bring to front | Shift+PgDown | Put the selection on top (and last when machining) |
| Send to back | Shift+PgUp | Put the selection at the bottom (and first when machining) |
| Bring forward |  | Move up one place |
| Send backward |  | Move down one place |

### Groups

| Command | Shortcut | Purpose |
|---|---|---|
| Group |  |  |
| Ungroup |  |  |
| Reverse the order |  | The objects of each group and the contours of each combined object go into reverse order (the machining order too) |
| Combine |  | Merge the selected objects into one shape |
| Break apart |  | Make one shape per contour |
| Nest |  | Combine outer and inner contours: each outer contour gets its holes (direction normalised for machining) |

### Modes

| Command | Shortcut | Purpose |
|---|---|---|
| Dimensions | F2 | Size and position; with a shape tool (rectangle, polygon, star, spiral…): the shape by its parameters; a selected shape: its parameters |
| Snap | Shift+F3 | Snap to nodes, midpoints, centres and grid (F3: snap window) |

### Snap

| Command | Shortcut | Purpose |
|---|---|---|
| Snap window | F3 | Snaps (TypeEdit: F3): enable, choose snap points, snap radius |
| Nodes |  | Snap: nodes |
| Intersections |  | Snap: intersections |
| Midpoints |  | Snap: midpoints |
| Centres |  | Snap: centres |
| Centroids |  | Snap: centroids |
| Quadrants |  | Snap: quadrants |
| Perpendicular |  | Snap: perpendicular |
| Tangent |  | Snap: tangent |
| Extension |  | Snap: extension |
| Parallel |  | Snap: parallel |
| Guides |  | Snap: guides |
| Mid between two points |  | During a tool: the next point is the midpoint of two clicked (snapped) points |
| From a point |  | During a tool: click a base point, then enter the offset (X, Y) of the wanted point |
| Intuitive snapping |  | Dimensioning: the cursor snaps to points, midpoints, centres and intersections even without snapping (F3) |
| On contour |  | Snap: on contour |
| Grid |  | Snap: grid |
| Tracking | F11 | Snap tracking (F11): hovering snapped points acquires them; the cursor then snaps to their vertical and horizontal lines, and to where they cross |
| Polar tracking | Shift+F12 | Polar tracking (Shift+F12): from the last clicked point, the cursor snaps to angles that are multiples of the step (15° by default; right-click the button: change the step) |

## View

### Mode

| Command | Shortcut | Purpose |
|---|---|---|
| Animation |  | The bodies of the 3D part in motion; joints, travel, direction and collisions in its window |

### Zoom

| Command | Shortcut | Purpose |
|---|---|---|
| Zoom all | Ctrl+0, Home, Ctrl+À |  |
| Selection |  | Zoom to selection |
| Zoom in | Ctrl+PgUp |  |
| Zoom out | Ctrl+PgDown |  |
| Refresh | Ctrl+W, Ctrl+R |  |
| Previous zoom |  | Back to the previous view (zoom, framing) |
| Zoom plate |  | Frame the plate |
| Zoom window |  |  |

### Contours

| Command | Shortcut | Purpose |
|---|---|---|
| Direction | Ctrl+7, Ctrl+È | Contour direction: closed in green (counter-clockwise) or blue (clockwise), open in black; arrow at the start and rank of each object |
| Fill | Ctrl+9, Ctrl+Ç | Closed contours filled with their tool colour |
| Engraving preview |  | Strokes at the real width of their tool (tool table): spots details too fine for the cutter or the laser |
| Grid | Ctrl+G |  |
| Start points |  | The start point of each displayed contour (filled square) |
| Control points |  | The points of all displayed contours: square for a corner, circle for a smooth point |

### Guides & rulers

| Command | Shortcut | Purpose |
|---|---|---|
| Rulers | Ctrl+Shift+R | Rulers; drag from a ruler to place a guide |
| Clear guides |  | Remove all guides (a single guide: drag it back onto a ruler) |
| Guides… |  | The list of guides in the drawing, to edit; guides spread over the plate |
| Object to guides |  | Each straight side of the selected objects becomes a guide; for a curve, the sides of its box |
| Origin |  | Drawing origin marker (X, Y); drag from the ruler corner to move it |
| Set origin… |  | Coordinate origin (rulers, F2 position, status bar): plate corner or centre, selection centre, typed values |
| Notes |  | Show the drawing's notes |
| Counter |  | Time spent on the document (kept in the file) in the status bar — for a quote; only counts while working (nothing after 5 minutes without action) |

### Display

| Command | Shortcut | Purpose |
|---|---|---|
| Layer tabs |  | One tab per layer above the workspace: choosing a layer shows it alone |
| Theme |  | 30 themes (5 light, 25 dark, including TypeEdit), your own and those of plugins |
| Dark mode |  | Switch from the preferred light theme to the preferred dark theme (F10 > Appearance) |
| Customize |  | Customize the interface: themes with preview, interface and workspace colours, import and export |
| Customize the ribbon |  | Your own tabs, named and placed where you want: your commands in groups, with the label you choose; shown tabs. Right-click a ribbon command: add it to one of your tabs |
| Collapse the ribbon | Ctrl+F1 | Ribbon reduced to its tabs (clicking a tab unfolds it for one command; double-click a tab: collapse or expand) |
| Colour-blind colours |  | CAM toolpaths and intersection marks in colours that can be told apart without red and green (Okabe–Ito palette) |
| Full screen | F12, Shift+F11 | VectorDrive on the whole screen, without title bar; F12 a 2nd time: the Windows taskbar stays visible and usable; a 3rd time: the window; remembered at the next start |
| Keep the taskbar |  | Full screen: the Windows taskbar stays visible and usable (VectorDrive without frame on the rest of the screen) |

## CAD

### Create

| Command | Shortcut | Purpose |
|---|---|---|
| Selection | Esc |  |
| Rectangle |  | Rectangle: drag from one corner to the other; Ctrl: square; Shift: from the centre |
| Ellipse |  | Ellipse: drag from one corner of its box to the other; Ctrl: circle; Shift: centred on the first point |
| Rectangle 3 points |  | Rectangle 3 points: two clicks for one side (it gives the tilt), a third for the other side; corners of the default rectangle |
| Line |  |  |
| Polyline |  |  |
| Polycurve |  | Polycurve: lines and arcs that follow on without a break. Tab: free lines, tangent arcs, tangent lines; Backspace: removes the last one; Enter to finish, click the first point to close it |
| Bézier |  |  |
| Curve through points |  | Curve through points: each click is a point a smooth curve passes through; double-click or Enter to finish, click the first point to close it |
| Double line |  | Double line: two parallel strokes, clicks as for a polyline; Ctrl+click on the tool: corner type, spacing on each side of the axis, line start and end |
| Break line |  | Break line: two clicks, the break symbol (zigzag) in the middle of the stroke |
| Polygon |  | Polygon: drag from the centre to a vertex (Ctrl: vertex on top); Shift: two opposite points; Alt: to the middle of a side (circumscribed polygon) |
| Polygon by edge |  | Polygon by edge: two clicks, the ends of an edge; the polygon (number of sides from the ribbon) lies to the left of the drawn edge, Ctrl: to the right |
| Star |  | Star: drag from the centre to a tip (Ctrl: tip on top); Shift: two opposite points on the circle |
| Spiral |  |  |
| 3-point arc |  | 3-point arc: start, through point, end; Shift on the third click: start, end, then the curvature; F2: type the points |
| Cut a contour |  | Cut a contour: drag a line across open or closed contours (those selected, otherwise all it touches); they are cut at each intersection and nothing moves. Tab or Shift: closed contours are closed along the line; Ctrl: at 45° |
| 3-point circle |  |  |
| Arc centre, start, end |  | Arc by centre, start, end: one click at the centre, one at the start (it sets the radius), one for the end; counter-clockwise, Ctrl: clockwise; F2: type the values |
| Circle 2 points |  | Circle 2 points: two clicks, the ends of a diameter |
| Ellipse by axis |  | Ellipse by axis: two clicks, the ends of an axis (it gives the tilt), then a click at the wanted distance from the centre for the other half-axis |
| Tangent circle |  | Tangent circle: click two straight lines, circles or arcs, near the tangent points — circle of the given radius tangent to both; radius 0: a 3rd click, circle tangent to all three |
| Construction line |  | Construction line: one click for the point, one click per line through it (Shift: by 15°) — infinite oblique guide, snapping on it and at crossings (F3); double-click to set it, dragged back onto a ruler: deleted |
| Marker |  |  |
| Pencil (recognised shapes) |  | Pencil: draw freehand — the stroke becomes the sketched line, rectangle, ellipse or triangle, otherwise a smoothed curve (Shift on release: smoothed curve only) |
| Blob brush |  | Blob brush: drag to paint a filled area that merges with the closed shapes of the current tool it touches; [ and ]: size |
| Slot |  | Slot (obround): overall length, width, angle — editable afterwards |
| Ring |  | Ring: outer and inner radii — editable afterwards |
| Sector |  | Ring sector or pie slice: radii, start angle, opening — editable afterwards |
| Gear |  | Involute gear: module, number of teeth, pressure angle, bore — editable afterwards |
| Symmetric curve (OX axis) |  | Curve in one piece, symmetric about the horizontal axis through the centre of the plate; closed by default, F opens it; Ctrl or Shift while moving: a corner or tangent point |
| Symmetric curve (OY axis) |  | Curve in one piece, symmetric about the vertical axis through the centre of the plate; closed by default, F opens it; Ctrl or Shift while moving: a corner or tangent point |
| Cyclic curve |  | Curve in one piece, centred on the plate and symmetric about both axes; closed by default, F opens it |
| Symmetric curve (origin) |  | Curve in one piece, symmetric about the centre of the plate; closed by default, F opens it |
| Symmetric drawing |  | Each drawn shape gets its reflection about the vertical axis through the middle of the plate; a stroke touching the axis is joined to its reflection |
| Cyclic symmetry |  | Each drawn shape is repeated as a rosette around the plate centre (adjustable number of copies) |
| Arrow |  | Arrow in four clicks: base of the tail, tip, size of the head, thickness of the tail; F2 or Ctrl+click: its dimensions as numbers |
| Tangents |  | Lines tangent to two selected circles, or their hull (belt, slot) |
| Note |  | Note (sticky) on the drawing: instruction for the workshop, never machined nor exported |
| Point by coordinates… |  | Give the drawing tool's next point by its coordinates (absolute or relative) |

### Text

| Command | Shortcut | Purpose |
|---|---|---|
| Text |  |  |
| On curve |  | Place the selected text on the selected curve, which disappears (Shift keeps it); a curve alone: a new text |
| On arc |  | Put the selected text on an arc, or a new text (on the selected circle or at the centre of the view); Ctrl+click: by the angles |
| In a frame |  | Text fitted in a rectangle (selected rectangle or dimensions) |
| In a shape |  | The text flows inside a closed shape, line after line, avoiding its holes. Select the shape, and the text to put in it if it already exists. Other, smaller selected shapes: it flows around them |
| Move along the curve |  | Move a text along its curve with the mouse; F2: from the start of the curve or from its current position |
| Characters |  | Character list of a font: insert a symbol (Ø, ±, °, ©…) into the selected text |
| Recognise a font… |  | Find the installed fonts closest to selected letters converted to curves, or to a picture: the last screenshot, the clipboard, a file |
| Fixed pitch |  | Fixed spacing: each character in a cell of the same width (aligned numbers) |
| Proportional |  | Proportional spacing, without kerning |
| Typographic |  | Typographic spacing, with kerning |
| Tight with kerning |  | Automatic kerning, without the space on either side of the letters |
| Tight |  | No kerning, and without the space on either side of the letters |
| Italic |  | Slanted text (12°) or upright |
| Underline |  | Underlined text (a bar under each line) or not |
| Italic and underline… |  | Italic angle, underline position and thickness |
| Letters… |  | Adjust each letter: kerning, offset, height, width, rotation, superscript and subscript |
| Letters with the mouse |  | Click: choose a letter of the text, drag: shift it. Arrows: shift; Alt+arrows: kerning; + and −: size; Page Up and Down: rotation; Del: back to normal; double-click: the Letters window |
| On multiple arcs |  | Text lines on arcs with the same centre: radius, angle, direction, simple, radial or inclined deformation |
| In columns |  | Spread the lines of the selected text into side-by-side columns |
| Rows and columns |  | Text in rows and columns: width, alignment and margins per column, borders; double-click reopens it |
| Variable text |  | Adds |Name| (variable, date or time) to the selected text, or a new variable text |
| Variables |  | Variable table (one row per state), series, data import, displayed state |
| Produce the states |  | One copy of the selection per row of the variable table, laid out on the plate; the originals are hidden |
| Change font |  | Change the font of the selected texts (or of all texts) |
| Add an SVG font… |  | A font in SVG format (free single-line fonts, Hershey for example) joins the font list |
| Font editor |  | Draw a font, single-line or not, character by character, or change one: the selection becomes the character |
| Text presets… |  | Text preset manager: create, change each setting, rename, duplicate, delete, import, export |
| To curves |  | Convert texts to curves |
| Spelling… |  | Checks the texts of the selection, otherwise of the whole drawing, with the Windows spell checker |
| Find / replace |  | Find and replace in texts (selection, otherwise the whole drawing) |
| Typographic punctuation |  | Chosen texts (otherwise all): French quotes « », apostrophe ’, ellipsis …, non-breaking spaces before ; : ! ? |
| Merge texts |  | Merge the chosen texts into one multi-line text, top to bottom (single-line texts of an imported drawing): font, height and line spacing kept |

### Measure

| Command | Shortcut | Purpose |
|---|---|---|
| Dimension |  |  |
| Arc length dimension |  | Arc length dimension: click an arc (its pieces joined), click to place the dimension arc — developed length, arc symbol above the number; Tab: other dimension type |
| Jogged radius dimension |  | Jogged radius dimension: click a circle or an arc, click to place the text, click where the line starts (centre off the sheet: large radius) — the line joins the radius with a jog |
| Dimension jog |  | Jog (zigzag) on the line of the selected linear dimensions: a length not to the drawing's scale; position 0: removed |
| Feature control frame |  | Geometric tolerance frame (flatness, position, runout…) with its value, material condition and datums; double-click to edit it |
| Inspection dimension |  | Make the selected dimensions inspection dimensions: frame around the value, label and inspection rate (none: removes the inspection) |
| Space dimensions |  | Selected parallel linear dimensions at a regular interval from the one nearest the object (interval 0: aligned with it) |
| Measure |  |  |
| Rectangle distance (X, Y, XY) | Shift+D | Rectangle distance (TypeEdit): click the start, click the end — the rectangle of both points, its X and Y sides and the XY diagonal (F3 snapping advised) |
| Measure a radius |  | Measure a radius: click a circle, an arc or a curve — radius and diameter, angle and length of an arc, radius of curvature of a curve at the clicked point |
| Measure an angle |  | Measure an angle: click two straight lines, on the side of the wanted angle; elsewhere, three clicks — the vertex then a point on each side (F3: snap to points) |
| Bounding frame | E | Rectangle right around the selection (or the whole drawing), no margin, at once |
| Bounding frame… |  | Rectangle (or ellipse) around the selection, with margin and rounded corners |

### Node mode

| Command | Shortcut | Purpose |
|---|---|---|
| Node mode |  |  |
| Delete node |  |  |
| Cut |  | Break the contour at the selected node |
| Join |  | Join two open contours |
| To line |  | Segments between the selected points → lines |
| To curve |  | Segments between the selected points → editable curves |
| Point on curve |  | Selected off-curve points → on-curve: the outline goes through them |
| Off curve |  | Selected on-curve points → off-curve: they pull the curve without it going through them |
| Smooth |  | Selected points smooth (aligned handles) |
| Symmetric |  | Selected points symmetric (aligned handles, same length) |
| Align H |  | Selected points at the same height |
| Align V |  | Selected points at the same abscissa |
| Average |  | Selected points gathered in one place: their average point (then Join to weld two open ends) |
| Start point |  | Point mode: the selected point becomes the start of its closed contour, and machining will begin there |
| Refine |  | A new point in the middle of each segment (path unchanged) |
| Add a point |  | Point mode: click on the contour, a red point appears, then this button or the + key |
| Simplify |  | Fewer points, at the chosen precision: set it with Ctrl or Shift |
| To segment |  | Point mode, two points of a contour: the part between them becomes a single straight line (Shift: the other part of a closed contour) |
| Portion as arc |  | Point mode, two points of a contour: the portion between them becomes the circular arc through its middle (Shift: the other portion of a closed contour) |
| To corner |  | Point mode, two points of a contour: the part between them becomes a corner, where the tangents meet (Shift: the other part of a closed contour) |
| Move a contour |  | Drag one contour of an object without breaking it apart (Ctrl: at 45°) |
| Vertical projection |  | Selected points projected vertically onto a reference (guide or contour): then click the reference |
| Horizontal projection |  | Selected points projected horizontally onto a reference (guide or contour): then click the reference |
| Orthogonal projection |  | Selected points moved to the nearest point of a reference (guide or contour): then click the reference |

### Reshape

| Command | Shortcut | Purpose |
|---|---|---|
| Cut and delete |  | Two clicks on a contour: the portion between them is removed. Closed: clockwise from one to the other, Tab: the other portion |
| Erase a contour |  | A click on a contour removes it without splitting the object; Shift: the original stays |
| Change to segment |  | Two clicks on a contour: the portion between them becomes a straight line; Tab: the other portion |
| Change to arc |  | Two clicks on a contour, then set the arc with the mouse and click; Tab: the other portion |
| Change to curve |  | Two clicks on a contour, then set the curve with the mouse and click; Tab: the other portion |
| Change to angle |  | Two clicks on a contour, then place the corner and click; Tab: the other portion |

### Trim

| Command | Shortcut | Purpose |
|---|---|---|
| Trim |  |  |
| Extend |  |  |
| Extend as arc |  | Extend as arc: one click near the end of a circular arc, then one click towards the point to reach, the first one the circle meets or a later one |
| Boundary |  | Boundary: clicking in an area closed by strokes (open or closed, crossing) creates its shape, islands as holes (Shift: without islands); right-click on the button: gap tolerated between strokes |
| Fillet between two strokes |  | Fillet between two strokes: click the 1st stroke then the 2nd, on the side to keep — extended or trimmed and joined by an arc (fillet radius; Shift: sharp corner) |
| Eraser |  | Eraser: drag to erase what it covers (shapes of the selection, otherwise all); [ and ]: smaller, larger |
| Chamfer between two strokes |  | Chamfer between two strokes: click the 1st stroke then the 2nd, on the side to keep — extended or trimmed and joined by a chamfer (chamfer size; Shift: sharp corner) |

### Distortions

| Command | Shortcut | Purpose |
|---|---|---|
| Zigzag |  | Make the outline wave on both sides of itself: points or rounded waves |
| Roughen |  | Randomly move the outline points: irregular edge, hand-drawn look |
| Pucker / bloat |  | Bloat: bulging sides; pucker: points outwards |
| Twist |  | Turn the drawing, more strongly near its centre |
| Scallops |  | Scalloped edge: regular arcs bulging outwards, meeting at the corners (plate frame, revision cloud) |

### Technical drawing

| Command | Shortcut | Purpose |
|---|---|---|
| Divide (marks) |  | Markers in equal parts along the chosen curve |
| Measure (marks) |  | A marker every n mm along the chosen curve |
| Lengthen |  | Lengthen or shorten an open contour: by Δ, to a length, or by a percentage |
| Change by a point |  | Click a point: the nearer end of each chosen straight line goes to it, each chosen circle passes through it (same centre), a text chosen alone is placed on it |
| Centre marks |  | A cross at the centre of each chosen circle or arc (with optional extension lines) |
| Center line |  | Center line: click two straight lines — a line on their axis, from the middle of their starts to the middle of their ends, slightly overshooting; solid or dash-dot (F10 › Drawing) |
| Crop marks |  | Crop marks at the corners and registration targets around the selection, otherwise the plate — to register a cut on a print |

### Symbols

| Command | Shortcut | Purpose |
|---|---|---|
| Library | Ctrl+Shift+Y | Library panel: symbols, DXF files and workshop drawings, sorted in folders |
| Library (window) |  | Library (TypeEdit: B) in its own full-screen window: folders, large thumbnails, preview; press B again to close it |
| Create symbol |  | Save the selection as a TypeEdit symbol (.smb) in the library |

### Trade tools

| Command | Shortcut | Purpose |
|---|---|---|
| Barcode |  | DataMatrix, QR Code, Code 128, Code 39, EAN-13 |
| Code plate |  | On two selected frames: the code in the larger one, its readable text in the other, each fitted to its frame; the text always follows the code |
| Texture creation |  | A pattern (chevrons, waves, scales… or your strokes) repeated by symmetry inside the closed contours |
| Vectorize |  | Contours of a black and white image (logo, stamp): selected image or file |
| Edit image |  | Open the selected image in this computer's image editor; each time it is saved, it is taken back into the drawing, in place |
| Hatching |  | Fill the selected closed contours with parallel lines (solid areas by laser or cutter) |
| Scribble |  | Fill the chosen closed shapes with a continuous zigzag (engraving in one stroke, without lifting) |
| Braille |  | French braille text (dots to engrave or drill) |
| Photo |  | Halftone photo: dots or lines following density |
| Dial |  | Graduations and numbers around a centre (selected circle or view centre) |
| Graduated ruler |  | Numbered graduated ruler, optional vernier |
| Holes |  | Drill holes (TypeEdit Hole object): selected circles become holes, or one hole at the centre of the view |
| Stamp |  | Prepare a rubber stamp: frame, border, shoulder, mirror, background to engrave (negative) |
| Equation curve |  | A curve drawn from formulas: x(t) and y(t), y = f(x) or polar; rose, heart, spiral… ready to use |
| Guilloche |  | Pattern of interlaced lines, as on a banknote or a dial: rosette, band, spirograph |

## CAD

### 3D views

| Command | Shortcut | Purpose |
|---|---|---|
| Engraver view | Ctrl+4, Ctrl+' | 3D part seen from the front and above, as from the machine |
| Isometric view | Ctrl+5, Ctrl+( | 3D part in isometric view |
| YZ view | Ctrl+2, Ctrl+É | Part in 3D seen from the side (YZ plane), no tilted perspective |
| ZX view | Ctrl+3, Ctrl+" | Part in 3D seen from the front (ZX plane), no tilted perspective |
| Lighting |  | Set the direction of the light in the 3D view |

### Create

| Command | Shortcut | Purpose |
|---|---|---|
| Dome |  | Domed relief of the selected closed shapes (TypeArt's galbe): height map to machine with Relief |
| Sweep |  | Sweep a profile along a path (select the path, then the profile): frame, moulding, tube |
| Dome |  | Dome on the selected markers: Gaussian, spherical or bell jar |
| Extruded relief |  | Inside of the selected closed shapes offset in Z (straight-sided step) |
| Revolved relief |  | A curve turned around an axis: two markers, or a straight line, selected with it |
| Facet |  | Inclined plane through three markers (given heights) inside the selected closed shapes |
| Sweep between two paths |  | Profile stretched between two paths (first path, second, profile; a second profile: transition from one to the other) |
| Prismatic mode |  | Letters or objects at constant Z, with the profile on their edge. Select the text or object, then the profile (an open curve) |
| Warp grid |  | The relief warped between four touching curves, or inside a closed contour, for a band or arc decoration. Select the relief and the curves |

### Combination

| Command | Shortcut | Purpose |
|---|---|---|
| Replace |  | Relief combination mode: replace |
| Add |  | Relief combination mode: add |
| Subtract |  | Relief combination mode: subtract |
| Maximum |  | Relief combination mode: maximum |
| Minimum |  | Relief combination mode: minimum |
| Average |  | Relief combination mode: average |
| Limit the change |  | New reliefs are only laid on the existing relief |
| Combine reliefs |  | Paste the selected reliefs into the first one (the current relief), using the combination mode |
| Relief probe |  | Relief probe: click = Z height of the relief at this point; second click = profile (min and max heights, steepest slope) |

### Touch-ups

| Command | Shortcut | Purpose |
|---|---|---|
| Smoothing |  | Smooth a galbe: the whole galbe, or the area of the shapes selected with it |
| Z alignment |  | Bring the top, middle or bottom of the relief to a height (inside the closed shapes selected with it, otherwise everywhere) |
| Dynamic adjustment |  | New max. Z of the relief and curvature of its profile (inside the closed shapes selected with it, otherwise everywhere) |
| Fit to volume |  | Stretch the relief heights between a min. Z and a max. Z (inside the closed shapes selected with it, otherwise everywhere) |
| Invert relief |  | Z mirror: bumps become hollows and hollows bumps (inside the closed shapes selected with it, otherwise everywhere) |
| Slice |  | Keep the relief between two heights (inside the closed shapes selected with it, otherwise everywhere) |
| Raise details |  | Accentuate small reliefs (unsharp mask) (inside the closed shapes selected with it, otherwise everywhere) |
| Bas-relief |  | Bring the relief to a shallow depth while keeping its details (inside the closed shapes selected with it, otherwise everywhere) |
| Fill holes |  | Fill closed hollows up to their rim (inside the closed shapes selected with it, otherwise everywhere) |
| Border |  | The chosen relief extended around the chosen closed shapes, over a width: continuing its edge, or flat at a given Z (without leaving the relief) |
| Edge facets |  | Around the relief, a slope runs from its edge down to zero: the steep edge softens |
| Erase a part |  | Keep only the relief inside the chosen closed shapes (Ctrl: erase the relief inside them) |
| Extract a part |  | The relief inside the chosen closed shapes becomes a separate, cropped relief; removed from the original (Ctrl: left in the original) |
| Slices |  | The contours of the chosen relief at successive heights (contour lines) — to recover the outline of a probed object |
| Place on |  | Place the second chosen relief on the first: lowest point or base plane at the level of the highest point below, or base plane following the surface |
| Wrap onto a relief |  | The second chosen relief, wrapped onto the first while keeping its dimensions along the surface: parallel, spherical or cylindrical, in one or several copies |
| Align a plane to zero |  | Relief probed askew: the plane through the relief under three chosen markers is brought to Z 0 (relief levelled) |
| Die/Punch |  | Punch and die (mirrored hollow imprint) of a relief, with a clearance (inside the closed shapes selected with it, otherwise everywhere) |
| Adapt to a tool |  | What the chosen tool can machine: drafted walls, too fine details filled (inside the closed shapes selected with it, otherwise everywhere) |
| Seamless texture |  | Make the relief seamless: its opposite edges join when tiled |

### SculptArt

| Command | Shortcut | Purpose |
|---|---|---|
| SculptArt |  | SculptArt: paint on a relief (add, dig, smooth, flatten, noise); brush settings: 3D > SculptArt > Brush |
| Brush… |  | SculptArt brush: type (add, dig, smooth, flatten, noise), radius, strength |

### Textures

| Command | Shortcut | Purpose |
|---|---|---|
| Relief from an image |  | An image (photo, logo) in relief: from black to white, at chosen heights (PhotoArt) |
| Relief from a 3D model |  | A 3D part (STL, STEP, 3D XML) seen from one side becomes a relief, combinable with the selected relief |
| 3D primitive |  | Sphere, ellipsoid, cone, lying cylinder, torus or box as a relief — on the chosen markers, at the centre of the chosen objects or relief; can be combined with the chosen relief |
| Profile dome |  | The chosen profile (open stroke: X = distance to the axis, Y = height) revolved around a vertical axis, at the chosen marker (otherwise its leftmost point), over a full turn or part of it |
| Bilinear surface |  | Ruled surface set by the heights of its four corners — over the bounding box of the chosen closed shapes (inside them), of the chosen relief or of the plate |
| Algorithmic texturing |  | Fractal texture (standard, focal, stripes, concentric) on the relief or inside the chosen closed shapes |
| Weave |  | Interlaced threads (two crossed layers) on the relief or inside the chosen closed shapes |
| Texture fill |  | Repeat a small relief (the pattern) as tiles inside the chosen closed shapes, on the chosen relief or as a new relief |

### Duplicate

| Command | Shortcut | Purpose |
|---|---|---|
| Linear multicopy |  | Copy the relief of an area (closed shape selected with it) in rows and columns, inside the relief |
| Circular multicopy |  | Copy the relief of an area around a centre (marker, otherwise the area centre) |
| Beading |  | Copy the relief of an area along a curve selected with it |

### Machining

| Command | Shortcut | Purpose |
|---|---|---|
| Relief |  | New toolpath: relief (on the selection, otherwise on the active layer's colour) |
| Relief sequence |  | New toolpath: relief sequence (on the selection, otherwise on the active layer's colour) |
| 3D finishing |  | New toolpath: 3d finishing (on the selection, otherwise on the active layer's colour) |

## Operations

### Booleans

| Command | Shortcut | Purpose |
|---|---|---|
| Union |  | Boolean operation: union (reference: 1st selected object); Ctrl or Shift: keep the originals |
| Intersection |  | Boolean operation: intersection (reference: 1st selected object); Ctrl or Shift: keep the originals |
| Difference |  | Boolean operation: difference (reference: 1st selected object); Ctrl or Shift: keep the originals |
| Exclusion |  | Boolean operation: exclusion (reference: 1st selected object); Ctrl or Shift: keep the originals |
| Divide |  | All the pieces bounded by crossing contours (each with the tool of the shape visible above) |
| Trim |  | Remove the parts hidden by the shapes above |
| Merge |  | Trim, then join neighbouring pieces of the same tool |
| Crop |  | The top shape frames the others, then disappears |
| Minus back |  | The top shape minus all the others |
| Shape builder |  | Shape builder: select overlapping shapes, then drag across their pieces to merge them (click: one piece on its own; Alt: delete the pieces touched) |

### Contours

| Command | Shortcut | Purpose |
|---|---|---|
| Offset |  | Contour offset |
| Clip |  | Cut what extends beyond the closed frame selected first, or otherwise beyond the plate; Ctrl: the crop type |
| Fit into frame |  | Scale the selected objects, centred in the frame selected first |
| Punch |  | The closed shape selected first cuts through the other objects (strokes cut at its edge, areas hollowed out); Ctrl: the punch type |
| Knife |  | Cut the selected closed shapes along the last selected stroke (line, polyline, curve or edge of a shape) |
| Shadow |  | Solid (extruded) or drop shadow of the selected closed contours, editable by double-click |
| Envelope |  | Distort the selection (texts included) into an arc, arch, bulge, pinch, wave or trapezoid, editable by double-click |
| Envelope from curves |  | Warp objects between four touching curves, or inside a closed contour. Select the objects, then the curves last; editable with a double-click |
| Bend along a path |  | The artwork follows a curve and deforms with it: stretched, at its own size or repeated. Select the objects, then the path last. Editable by double-click |
| Double line |  | Replace each stroke with two parallel strokes (exact parallel curves) |
| Dashes |  | Turn the strokes into real dashes of a linetype (dashed cutting, folding, perforation): standard types, .lin file or own pattern |
| Fillets |  | Round the corners (in node mode: the selected nodes) |
| Chamfers |  | Chamfer the corners (in node mode: the selected nodes) |
| Live corners |  | A handle in each angle of the chosen shapes: drag it to round. Click: choose a corner; Alt+click: round, inverted, chamfer; double-click: type the radius; Del: sharp corner |
| Liquify |  | A brush that deforms the chosen shapes, otherwise every shape it meets. Brackets: brush size |
| Brush settings… |  | Liquify: what the brush does, its size, its strength and the detail it adds |
| Blend |  | Join two open strokes with a tangent arc (or a sharp corner if the radius is zero), extending or trimming them |
| Curve bridge |  | Connect the nearest ends of two open strokes (or both ends of one stroke) with a curve continuing them, tangent or smooth; the strokes stay whole |
| Outline stroke |  | Replace a stroke by the outline of its width |
| Variable width |  | Replace a stroke with a band of variable width: from the start width to the end width, tapered at both ends or wavy (thick and thin strokes, leaves, points) |
| Width tool |  | On a stroke: click, a width point; drag, its width (Alt: one side only; Ctrl: move it along the stroke); Del: remove it; Enter or double-click: confirm, the stroke becomes a filled band |
| Calligraphic nib |  | The chosen strokes, as drawn by a flat nib: wide across the nib, thin along it |
| Intersections |  | Detect intersection points (selection, otherwise the whole drawing) and remove them: small loops, normalize, union, outer outline, split at intersections |
| Loop eraser |  | Remove the small loops where a contour crosses itself |
| Clean up overlaps |  | Overlapping straight strokes (edges drawn twice, adjoining shapes): merged so they are engraved only once, per tool |
| Arcs and lines |  | Replace Bézier curves with tangent circular arcs and lines |
| Approximation |  | Replace runs of small segments with smooth curves (DXF, tracing) |
| Segmentation |  | Replace curves with straight segments |

### Transform

| Command | Shortcut | Purpose |
|---|---|---|
| Mirror H |  | Left-right symmetry (vertical axis; TypeEdit's vertical mirror, M); Shift: keep the original; Ctrl: axis on the right side |
| Mirror V |  | Top-bottom symmetry (horizontal axis; TypeEdit's horizontal mirror, Shift+M); Shift on the button: keep the original; Ctrl: axis at the base |
| Rotate 90° |  |  |
| Mirror about axis |  | Symmetry of the objects about the straight line, or the two markers, selected last; Ctrl or Shift: keep the originals |
| Rotate −90° |  |  |
| Rotation… | Shift+R | Rotate the selection by any angle |
| Move… |  | Move the selection by a given distance, or place a copy |
| Repeat transformation | Ctrl+Alt+T | Applies the last move, rotation or scaling to the selection again, whether done with the mouse or the keyboard |
| Repeat and copy | Ctrl+Alt+Shift+T | Like Repeat transformation, on a copy: move an object, then repeat once for each copy wanted |
| Transform each object… |  | Moves, scales or rotates each selected object around itself |
| Vertical axis |  | Straighten: rotate the selection around a point (1st click) so that another point (2nd click) is vertically above it; F3: snap to points |
| Horizontal axis |  | Straighten: rotate the selection around a point (1st click) so that another point (2nd click) is level with it; F3: snap to points |
| Align by points |  | Align by points: 1st source point, its destination, 2nd source point, its destination (Shift on the last click: scaled too; Enter after two clicks: move only) |
| Stretch |  | Stretch: two corners of a crossing window, then a base point and its destination; nodes inside the window move, segments to the others stretch (shapes of the selection, otherwise all) |
| Scale by reference |  | Scale by reference: base point, end of the reference length, then the new length (3rd click from the base point, or Enter to type it) |
| Rotate by reference |  | Rotate by reference: centre, reference direction (an edge of the object), then the wanted direction (3rd click, or Enter to type the angle) |

### Alignment

| Command | Shortcut | Purpose |
|---|---|---|
| Left |  | Align: left |
| Centre H |  | Align: centre h |
| Right |  | Align: right |
| Top |  | Align: top |
| Centre V |  | Align: centre v |
| Bottom |  | Align: bottom |
| Centres |  | Align: centres |
| Left outside |  | Place to the left of the first selected object |
| Right outside |  | Place to the right of the first selected object |
| Top outside |  | Place above the first selected object |
| Bottom outside |  | Place below the first selected object |
| Centre on plate |  | Centre the selection on the plate |
| Center on origin | Alt+W | Center the selection on the origin (TypeEdit: Alt+W) |
| Centre on plate H |  | Centre the selection horizontally on the plate |
| Centre on plate V |  | Centre the selection vertically on the plate |
| Plate left |  | Each object against the left margin of the plate |
| Plate right |  | Each object against the right margin of the plate |
| Plate top |  | Each object against the top margin of the plate |
| Plate bottom |  | Each object against the bottom margin of the plate |
| Distribute H |  | Equal spacing (the first and last objects stay in place) |
| Distribute V |  | Equal spacing (the first and last objects stay in place) |
| Centres H |  | Equal spacing (the first and last objects stay in place) |
| Centres V |  | Equal spacing (the first and last objects stay in place) |
| Space H |  | Objects placed left to right with a set gap |
| Space V |  | Objects placed bottom to top with a set gap |
| Same width |  | Give the objects the dimensions of the object selected first |
| Same height |  | Give the objects the dimensions of the object selected first |
| Same size |  | Give the objects the dimensions of the object selected first |

### Contours

| Command | Shortcut | Purpose |
|---|---|---|
| Close |  | Close open contours |
| Open |  | Open closed contours |
| Reverse direction |  | Reverse the direction of the selected contours |
| Overlaps | À | Remove overlapping contours (duplicates), at once with the last settings; Ctrl+click: the window |
| Duplicate points |  | Remove coincident points from the selected contours (zero-length segments) |
| Aligned points |  | Remove aligned points: consecutive straight lines merged (DXF, vectorized contours) |
| To circles |  | Nearly round closed contours (DXF polygons…) replaced by exact circles |
| Convert curves |  | Replace each selected contour with the closest circle, ellipse or rectangle; Shift: the original stays |
| Chain |  | Connect open contours whose ends touch (DXF import…) and close the loops; Ctrl+click: the distances |
| Explode |  | Each segment of the selected objects becomes a separate stroke |
| Remove contours |  | Remove holes, outer contours or contours smaller than a size |

### Duplicate

| Command | Shortcut | Purpose |
|---|---|---|
| Duplicate | Ctrl+Shift+D | Linear, grid or circular duplication |
| Linked copy | Alt+D | A copy that follows the shape of its original: editing the original edits its copies; each one keeps its place |
| Unlink copy | Alt+Shift+D | The linked copy becomes an independent object again |
| Select original |  | Selects the original of the linked copy |
| Scaled duplication |  | Copies along a curve, from the size of one object to that of another (selection: start object, end object, then the curve) |
| Free duplication |  | Free duplication: the selection follows the pointer; each click places a copy (its centre at the clicked point); Esc to finish |
| Linear duplication |  | The number of columns and rows, then drag: the copies follow as dashed outlines; Tab: the last one at the pointer; F2: as numbers |
| Circular duplication |  | The number of instances, then drag to the centre of the circle (F3 snapping included); F2: as numbers |
| Interpolate between two objects |  | The in-between shapes of two selected shapes, in selection order, at their places |
| Multi-copy |  | Fill the plate with as many copies of the selection as possible |
| Nest |  | Pack the selected objects tightly on the plate (further plates to the right if needed) |
| Nested copy |  | As many copies of each object as needed, laid out on as many plates or planes as it takes: count per object, starting point, direction |
| Nest into a contour |  | The objects are placed inside a closed contour, by their true shape. Select the contour first, then the objects. In a group or a combination: contour after contour |
| Copy into a shape |  | Copies of the objects fill a chosen shape, following their true shape. Select the objects, then the shape to fill last |
| Plate remnant |  | The part of the plate left free by the objects becomes a shape, on its own layer: ready for another nesting or to keep in the library |
| Cut up the remaining material |  | A grid of cut lines on what remains of the plate, so that it falls away in small pieces: around the selection, otherwise the active layer |
| Nesting report |  | A PDF: the settings of the last nesting, then each filled layer, with its areas and its drawing |
| Marquetry |  | Male and female forms for marquetry or inlay, each on its own layer |
| LED |  | LED positions for a sign: on the selected contours (axis spacing or count per contour, corners) or as a grid inside |
| Script |  | Draw with a VBScript script: the same functions as TypeEdit's shape scripts (NewCurve, MoveTo, LineTo, ArcHTo, ArcTTo, ClosePath, DbApi, WndScriptApi) |
| Constrained sketch… |  | Draw with constraints and dimensions: horizontal, tangent, equal, 40 mm… The figure recalculates. Double-click to edit it again |
| Perforate |  | Round holes, staggered or on a square grid, in the selected closed outlines (cut-outs stay clear), kept a margin away from the edges and from the selected open lines, such as bend lines |

### Measure

| Command | Shortcut | Purpose |
|---|---|---|
| Check |  | Check the drawing before engraving: off the plate, almost closed contours, duplicates, specks… |
| Purge |  | Remove what engraves nothing: empty shapes and texts, empty groups, empty layers |
| Perimeter |  | Measure the perimeter |
| Area |  | Area of closed contours |
| Mass properties |  | Area, perimeter, centroid, moments of inertia of the chosen closed shapes |
| Dimension | Shift+C | Shift+C: a chosen dimension → its settings; chosen objects (a frame…) → their automatic dimensions (settings and templates); nothing chosen → dimension between two points (Tab: other dimension type) |
| Quick dimensions |  | Dimension the selected objects in one go: X positions below and Y positions on the left (circle centres, corners of the others), continued or from a baseline |

## 3D Design

### Create

| Command | Shortcut | Purpose |
|---|---|---|
| Extrude |  | The selected closed shapes pulled into solids (height, draft angle, start height); holes stay holes. One side, symmetric, two sides or through the selected solids; new solids, or joined to the selected solids, cut from them or kept where shared |
| Revolve |  | The chosen closed shapes revolved around an axis (two markers, or a straight line chosen with them; otherwise the vertical through their leftmost point) |
| 3D sweep |  | Closed profiles pulled along a path (choose the path first, then the profiles): tube, moulding, handrail; optional twist and end scale |
| 3D loft |  | Solid through the chosen closed outlines, stacked in the order chosen (bottom first); ruled or smooth |
| Box |  | Solid: box (length, width, height) — on the chosen markers, at the centre of the chosen objects, otherwise at the centre of the plate |
| Corner |  | Solid: wedge — box cut on a slant, full height on one side — on the chosen markers, at the centre of the chosen objects, otherwise at the centre of the plate |
| Cylinder |  | Solid: cylinder with a vertical axis — on the chosen markers, at the centre of the chosen objects, otherwise at the centre of the plate |
| Cone |  | Solid: cone or truncated cone (top radius) — on the chosen markers, at the centre of the chosen objects, otherwise at the centre of the plate |
| Sphere |  | Solid: sphere — on the chosen markers, at the centre of the chosen objects, otherwise at the centre of the plate |
| Pyramid |  | Solid: pyramid or frustum, any number of sides — on the chosen markers, at the centre of the chosen objects, otherwise at the centre of the plate |
| Torus |  | Solid: torus (ring) — on the chosen markers, at the centre of the chosen objects, otherwise at the centre of the plate |
| Wall |  | Wall of given width and height along the chosen strokes (left of, centred on or right of the stroke) |
| Tube |  | Solid or hollow pipe (diameter, wall) along the selected lines, resting on the plane or at a given height |
| Frame member |  | Frame members (flat bar, round bar, tubes, angle, channel, I-beam) laid along the selected lines with mitred corners, or standing as posts on the selected markers |
| Coil |  | Coil with a vertical axis: a round or square section wound in a helix (diameter, pitch, turns), on the selected markers or circles (their diameter), otherwise at the centre of the plate |
| Thread |  | Modelled ISO thread: threaded rod on the selected markers or circles, or tapped holes in the selected solid at those places (M8, M8x1…; empty: from the circle's diameter) |
| 3D hole |  | Holes in the selected solid, from its top, on the selected markers or circles (their diameter): plain, counterbored or countersunk; blind (optional drill point) or through |
| Rib |  | Wall of a given thickness along the selected lines, joined to the selected solid: from its bottom to its top (or a height), extended from one wall to the other |
| Emboss on cylinder |  | The selected closed shapes and texts, drawn above a lying cylindrical solid (X or Y axis), wrapped onto it: embossed or engraved |

### Modify

| Command | Shortcut | Purpose |
|---|---|---|
| Press / pull |  | The closed shapes chosen with a solid, placed on its top: pulled upwards (added) or pushed into the material (cut) |
| History… |  | The steps of the chosen solid: go back to a setting or a sketch, suspend a step. The solid recalculates, in place |
| Shell |  | The selected solids hollowed out: walls of a given thickness, inside, outside or on both sides; closed or open on one or more sides (top, bottom, X, Y) |
| Round edges |  | All sharp edges of the chosen solids rounded to the given radius (convex ones, and concave ones if wanted) |
| Fillets and chamfers… |  | Round or chamfer only the edges you click on the volume |
| Draft… |  | Tilt the faces you click on the volume, so that it comes out of the mould |
| Move faces… |  | Change a diameter or a depth, or move a hole, by clicking its faces on the volume |
| Delete faces… |  | Plug a hole, erase a pocket or a boss, by clicking its faces on the volume |
| Offset solid |  | The chosen solids grown (rounded edges) or shrunk by a given distance |
| Smooth mesh |  | The chosen solids smoothed: facets subdivided, edges sharper than an angle kept |
| Cut |  | The selected solids cut by a horizontal plane (Z), a vertical one (X, Y) or a vertical one through a line selected with them; keep one side or both |
| Separate |  | The disjoint bodies of a solid as separate solids |
| Move in Z |  | Raise or lower the chosen solids |
| Align |  | The selected solids aligned on the first one selected, which stays put: sides or centres aligned, against it, on top or underneath, axis by axis |
| 3D rotate |  | The chosen solids rotated around an X, Y or Z axis through their centre |
| Swap the planes |  | X Y Z becomes Z X Y at each click, on the spot: three clicks give the original part back. With Shift, the original stays and the result lands beside it |
| 3D scale |  | The selected solids scaled, by one factor or per axis (shrinkage compensation…), about the centre of their bottom, their centre or the origin |
| Mirror in Z |  | The chosen solids flipped by a horizontal plane (copy possible) |
| Array in Z |  | Copies of the chosen solids stacked in height (count, step, rotation from one to the next: spiral staircase…) |

### Combine

| Command | Shortcut | Purpose |
|---|---|---|
| Union |  | The chosen solids joined into one |
| Subtract |  | The first chosen solid, minus the next ones |
| Intersection |  | The part common to the chosen solids |
| Cells |  | The pieces bounded by the selected solids (inside some, outside the others) and the voids they enclose (the cavity of a closed mould), as separate solids |

### Sheet metal

| Command | Shortcut | Purpose |
|---|---|---|
| Bent sheet |  | Upright bent sheet along the selected chains of straight lines, bends at the inside radius, and its flat pattern (K-factor) with the bend lines |
| Sheet metal tray |  | Sheet metal tray in the selected convex outlines: flat base, a flange bent up 90° on every side, open corners, and its cross-shaped flat pattern (K-factor) with the bend lines |
| Fold sheet |  | The blank drawn flat (selected closed contours, holes included) folded along the selected lines, at the inner radius, on the smaller side of each line; the bend zone follows the K factor |

### Plastic

| Command | Shortcut | Purpose |
|---|---|---|
| Boss |  | Plastic boss on the selected solid, standing on the top of the material at the selected markers or circles: drafted post, hole, radial ribs |
| Lip or groove |  | Raised lip or cut groove along the rim of the selected open shelled solids, against the inner or outer edge: the lip of one half fits into the groove of the other |
| Snap fit |  | Hooked snap fits at the selected markers: an upright cantilever arm standing on top of the selected solid and joined to it, or a separate solid |
| Rest |  | Rests at the selected markers: round or rectangular pads, solid or hollow, with draft, standing on top of the selected solid and joined to it, or separate solids |

### Inspect

| Command | Shortcut | Purpose |
|---|---|---|
| Mass properties |  | Volume, area, centre of gravity, bounding box and mass of the chosen solids |
| Bounding solid |  | Box or cylinder around the selected solids, grown by a margin: the part's stock |
| Section |  | 2D outline of the chosen solids at a given height |
| Flat shot |  | 2D outline of the chosen solids seen from the top, front or side, placed to their right |
| Interference |  | The chosen solids that overlap: common volume of each pair (and as solids) |
| Clearance |  | The selected solids that overlap, touch or are closer than a given clearance (distance and place), and each one's nearest neighbour |
| Compare solids |  | Two versions of a part laid over each other: surface deviation (largest, mean, place) and regions of material only in the first or only in the second |
| Surface analysis |  | The 3D part in colours: draft of its faces toward a pull direction (green, yellow, red), or faces reached along a direction, vertical tool or pull (green, red) |

### Exchange

| Command | Shortcut | Purpose |
|---|---|---|
| Import a solid |  | An STL file (closed mesh) added to the drawing as a solid |
| Solid to relief |  | The chosen solids seen from above as a relief (height map) — to machine with the 3D toolpaths (Relief, Finishing) |
| Relief to solid |  | The chosen reliefs as solids (with a base) — for booleans and STL export |

## STEP design

### Generators

| Command | Shortcut | Purpose |
|---|---|---|
| Generate a STEP part |  | Screws, nuts, washers, pins, bearings, keys, spur gears, bars, drilled plates, mould components: a STEP part with true faces, from the standards |
| Fasteners |  | Socket head, hex head, countersunk, button head and set screws, nuts, washers, pins (ISO standards) |
| Power transmission |  | Deep groove ball bearings, keys, spur gears |
| Stock and profiles |  | Bars, tubes, profiles, drilled plates, spacers, bushes |
| Mould components |  | Ejector pins, guide pillars and bushes, locating rings |
| Workholding |  | Strap clamps, step blocks, soft jaws, studs, T-slot nuts |
| Edit generated part… |  | The selected drawing part, added by the generators, reopened with its values: edit it, then replace it in place |
| Part from drawing… |  | The closed shapes picked in the drawing (and texts) as a STEP part with true faces: thickness, inner contours as through holes or pockets; one part per outline |
| Turned part from drawing… |  | A closed half-profile picked in the drawing, turned around the straight line picked with it (otherwise its left edge): a STEP part of revolution with true faces |

### 3D selection

| Command | Shortcut | Purpose |
|---|---|---|
| Faces |  | A click in the 3D view chooses a face (Ctrl or Shift: several, a second click removes it) |
| Similar faces |  | In the 3D view, all faces like the selected ones: holes of the same diameter, coplanar faces, identical countersinks or fillets |
| Parallel faces |  | A plane: all the planes with the same normal, at any height (the floors facing the tool); a cylinder: all those with a parallel axis (the holes drilled that way) |
| Coaxial faces |  | A cylinder, a cone or a sphere: all the faces on the same axis and the flat floors between them (a whole hole: through hole, counterbore, countersink, floor; a whole shaft) |
| Tangent faces |  | Step by step, the faces that follow the picked ones without a sharp edge: a rounded edge (sides and corner fillets), a chain of fillets |
| Body faces |  | All the faces of the bodies of the picked faces (one part of a mould) |
| Invert within the body |  | The faces of the picked bodies that are not picked: the rest of a part (everything but the floors already machined, but a hole) |
| Measure selection |  | The faces selected in the 3D view described (diameter, axis, normal, area); for two faces, their distance or angle |
| Clear the selection |  | No face or contour chosen any more (Esc in the 3D view) |

### Edit a STEP

| Command | Shortcut | Purpose |
|---|---|---|
| STEP bodies… |  | The bodies of a STEP file (the drawing's 3D part, otherwise a file to choose): extract, one file per body (a three-part mould: three STEP files), move; exact geometry |
| Combine STEP files… |  | Several STEP files combined into a single part, each body in its place |
| Repeat bodies… |  | The bodies of a STEP file (the drawing's 3D part, only the picked body) copied in a line at the given step, or in a circle around the vertical, into a new STEP file; exact geometry |
| Screw in this hole… |  | The wall of a hole picked in the 3D view of a STEP part: the hole recognised (clearance, counterbored, countersunk, tapped), the standard screw proposed and placed, saved alone or with the part |
| Part in this hole… |  | The wall of a bore picked in the 3D view of a STEP part: dowel pin, bearing, plain bushing, guide bushing, guide pillar, ejector pin or locating ring proposed at its diameter and placed, saved alone or with the part |

### STEP library

| Command | Shortcut | Purpose |
|---|---|---|
| Browse the library |  | The STEP library in the thumbnail browser: open a part or place it in the drawing |
| Library folder… |  | Choose the folder where STEP parts are saved and sorted |

## Formatting

### Text

| Command | Shortcut | Purpose |
|---|---|---|
| Back |  | End of text: the Select tool, and the previous tab |
| Text |  |  |

### General

| Command | Shortcut | Purpose |
|---|---|---|
| Characters |  | Character list of a font: insert a symbol (Ø, ±, °, ©…) into the selected text |

### Font

| Command | Shortcut | Purpose |
|---|---|---|
| Recognise a font… |  | Find the installed fonts closest to selected letters converted to curves, or to a picture: the last screenshot, the clipboard, a file |

### Text position

| Command | Shortcut | Purpose |
|---|---|---|
| Left |  | Line alignment of the selected texts |
| Centred |  | Line alignment of the selected texts |
| Right |  | Line alignment of the selected texts |
| Justified |  | Justified lines: each stretched to the width of the longest (space spread between the letters) |
| Coil |  | Spring (Tab key while typing): the free space of the line — up to the forced width, otherwise the longest line — is shared between its springs, to align, center, distribute |
| Vertical text |  | Letters one below the other (or back to horizontal) |
| Right to left |  | Right-to-left text, or back: display order and joined Arabic forms, if the font has them |
| UPPERCASE |  | Texts in uppercase |
| lowercase |  | Texts in lowercase |
| Capitalize Words |  | First letter of each word in uppercase |
| Small caps |  | Lowercase letters as reduced capitals (or back to lowercase), the text staying editable |
| Original case |  | Put the text back in the case it had before the case changes |

### Baseline

| Command | Shortcut | Purpose |
|---|---|---|
| On the baseline |  | Text standing on its baseline (as usual) |
| Under the baseline |  | Text under its baseline: the top of the capitals comes on the line |
| Fixed line spacing |  | In mm from one baseline to the next, whatever the text height |
| Proportional line spacing |  | A percentage of the text height, added to it; it follows the height |
| Typographic line spacing |  | A percentage of the full height of the font, descenders included; it follows the height |
| Line compression |  | Maximum length: each line that is too long is condensed on its own |
| Paragraph compression |  | Maximum length: all lines condensed by the same factor, that of the longest |
| Global compression |  | All lines tightened by the same factor, to fit in a percentage of the length of the longest |

### Tools

| Command | Shortcut | Purpose |
|---|---|---|
| Find / replace |  | Find and replace in texts (selection, otherwise the whole drawing) |
| Change font |  | Change the font of the selected texts (or of all texts) |
| Copy formatting |  | The formatting of the first selected text goes to the others (only one: to the texts clicked next) |

### Presets

| Command | Shortcut | Purpose |
|---|---|---|
| Save preset… |  | The format of the selected text (with no selection: that of new texts) saved under a name |
| Text presets… |  | Text preset manager: create, change each setting, rename, duplicate, delete, import, export |

## CAM 2D

### Machining

| Command | Shortcut | Purpose |
|---|---|---|
| CAM panel |  | Cutting tools, operations, toolpaths, post-processing |
| Tool library |  | Tools: library, dimensions, online catalogues, DXF and STEP drawings, import and export (TypeEdit, NeoDrive, CSV, ISO 13399) |
| Compute toolpaths |  | Compute the toolpaths of the active operations |
| Post-process… |  | Write the machine program (simulate before machining) |
| Panels… |  | Job larger than the plate or the table: split it into panels, one program per panel |
| Manual tabs |  | Manual tabs: a click near the contour of a closed shape places a tab (used by profiling, width and height of the operation); a click on a tab removes it |
| Lead-in and lead-out of a contour |  | Lead-in and lead-out of a contour: a click near a closed contour puts the start there and asks for its lead-in and lead-out, instead of those of the operation (0: none); a click on a mark changes or removes them |
| Operations full screen |  | The tools, operations and toolpaths window over the whole workspace, opacity adjustable to see the drawing below; the wheel still zooms the drawing |
| Create toolpath full screen |  | The “Create toolpath” window over the whole workspace, adjustable opacity; the wheel still zooms the drawing |

### View and simulate

| Command | Shortcut | Purpose |
|---|---|---|
| 2D toolpaths |  | Computed toolpaths on the drawing |
| Simulate machining |  | Material removal simulation of the ticked toolpaths |
| Volume measurement |  | Volume of the selected reliefs, otherwise volume of material removed by the checked toolpaths (simulation) |
| Special tool |  | Create a form tool: select its profile (open stroke, from tip to shank), then two markers one above the other on the tool axis |
| Local projection |  | Lay the toolpath of the chosen operation on a 3D part along a guide curve: select the curve (on the top view of the part), then this command |
| Toolpaths to drawing |  | The checked toolpaths (tool centre) become drawing strokes, in a “Toolpaths” layer, to edit or export them |
| Setup sheet |  | Workshop sheet to print: plate, tools, operations in order, estimated times, warnings and toolpath view (HTML) |
| Rest material |  | Preview: the areas of the chosen closed shapes that the tool cannot clear (corners, narrow passages), placed as surfaces on a separate layer |
| Read an ISO program… |  | An ISO program (G-code) from another machine or software shown among the toolpaths, to view and simulate it before running it |
| View a program in 3D… |  | Machine program (ISO, Heidenhain, and plugin languages: SimPL…) read and shown alone in 3D wireframe, to check it before running it |

### Toolpaths

| Command | Shortcut | Purpose |
|---|---|---|
| TypeEdit toolpaths… |  | Show the TypeEdit toolpaths (.000, .001…) of a VND |
| Clear toolpaths |  |  |
| Cylindrical wrap |  | Wrap the selected operation's toolpath onto a cylindrical part lying down (3-axis machine: Z follows the surface) |
| Conical wrap |  | Wrap the selected operation's toolpath onto a conical part lying down (3-axis machine: Z follows the surface) |
| Parallel projection |  | Project the selected operation's toolpath onto the surface of a STEP part (3-axis machine: Z follows the surface) |
| Merge toolpaths |  | The operations using the same tool as the chosen one follow it: fewer tool changes |

### Cutting

| Command | Shortcut | Purpose |
|---|---|---|
| Staggered circles |  | Cutting strategy: geometry to cut a sheet into parts (common lines between neighbouring parts) |
| Octagons |  | Cutting strategy: geometry to cut a sheet into parts (common lines between neighbouring parts) |
| Pie portions |  | Cutting strategy: geometry to cut a sheet into parts (common lines between neighbouring parts) |
| Rectangles |  | Cutting strategy: geometry to cut a sheet into parts (common lines between neighbouring parts) |
| Triangles |  | Cutting strategy: geometry to cut a sheet into parts (common lines between neighbouring parts) |
| Washer |  | Cutting strategy: geometry to cut a sheet into parts (common lines between neighbouring parts) |

## CAM 3D

### 3D part

| Command | Shortcut | Purpose |
|---|---|---|
| Place 3D part |  | STEP, STL or 3D XML part: face toward the tool, rotation, position on the plate — for the top view, the 3D view and 3D machining |
| Stock… |  | Block, round bar or plate the 3D part is machined from |
| Clamping… |  | Vise, chuck, clamps, blocks of the setup shown in the 3D view |
| To volumes |  | Each body of the part becomes a volume of the drawing (repaired mesh), to edit with the 3D tools and then machine |

### Click in the view

| Command | Shortcut | Purpose |
|---|---|---|
| Faces |  | A click in the 3D view chooses a face (Ctrl or Shift: several, a second click removes it) |
| Closed contours |  | A click in the 3D view chooses the nearest closed contour (Ctrl or Shift: several) |
| Points and dimensions |  | A click in the 3D view shows the point under the cursor and its coordinates |
| Clear the selection |  | No face or contour chosen any more (Esc in the 3D view) |

### 3D machining

| Command | Shortcut | Purpose |
|---|---|---|
| Automation… |  | Roughing, semi-finishing, finishing… in one go, tools proposed from the part — in the shown setup, on the selection, otherwise the whole part (or body) |
| 3D roughing |  | Z levels on the chosen faces and contours, otherwise on the whole part (or body) of the shown setup |
| 3D sweep |  | Passes following the surface, on the chosen faces and contours, otherwise on the whole part |
| Constant levels |  | Around the chosen walls at each height (finishing of steep walls) |
| Pocket to the floor |  | Flat floor picked: its contours into the drawing and a pocket down to its depth |
| Holes → drilling |  | Vertical cylindrical holes of the part: one circle per hole in the drawing and one drilling per diameter, at the depth of the hole |
| Contours into the drawing |  | The closed contours of the selection become shapes of the drawing, to machine in 2D |
| Zone of an operation |  | The selection becomes the zone of a 3D operation, or the zone of an operation becomes the selection |

### Machining

| Command | Shortcut | Purpose |
|---|---|---|
| Machining list |  | Right of the 3D view: the machining of the shown setup, their tool, their toolpath — double-click to edit, Del to delete |
| Edit machining… |  | The form of the machining picked in the list: strategy, tool, passes, stock to leave, slopes, area…; its toolpath is recomputed |
| Machining tool… |  | Diameter, cutting length, feed, speed… of the tool of the picked machining; the toolpaths of the machining that use it are recomputed |
| Delete machining |  | The picked machining and its toolpath deleted (Undo brings it back) |

### Place on

| Command | Shortcut | Purpose |
|---|---|---|
| Rest on this face |  | The chosen flat face at the bottom, on the table: the top towards the tool, part aligned with the axes |
| Face towards the tool |  | The chosen flat face turned towards the tool |
| Body placed on its own… |  | The body of the tab (or of the chosen faces) placed on its own for machining: face towards the tool, rotation, position; its toolpaths come back onto the assembly |
| 2D surface |  | The chosen face, turned towards the tool, becomes a sub-tab of the drawing with its outline as a guide: what is drawn there is machined in this setup |

### Bodies and colours

| Command | Shortcut | Purpose |
|---|---|---|
| Bodies |  | Bodies of the part: show or hide them |
| Show all |  | All bodies of the part shown |
| Colour per body |  | One colour per body of the part |
| Mechanisms… |  | Contacts and joints between bodies (slide, pivot, rest…), free motion, animation, collisions |
| Colours |  | Colour of the part, of the edges (remembered), original colours |

### Compute and view

| Command | Shortcut | Purpose |
|---|---|---|
| Compute toolpaths |  | Compute the toolpaths of the active operations |
| 3D toolpaths |  | Computed toolpaths in 3D, above the material (plunges, rapids, depths) |
| 3D simulation |  | Material removal of the computed toolpaths, in 3D |

## Options

### Options

| Command | Shortcut | Purpose |
|---|---|---|
| General |  | Options (F10), “General” tab |
| Appearance |  | Options (F10), “Appearance” tab |
| Drawing |  | Options (F10), “Drawing” tab |
| Display |  | Options (F10), “Display” tab |
| Files |  | Options (F10), “Files” tab |
| CAM |  | Options (F10), “CAM” tab |
| Proof |  | Options (F10), “Proof” tab |
| Printing |  | Options (F10), “Printing” tab |
| Updates |  | Options (F10), “Updates” tab |
| Plugins |  | Options (F10), “Plugins” tab |
| Performance |  | Options (F10), “Performance” tab |

### Configuration

| Command | Shortcut | Purpose |
|---|---|---|
| Options | F10 |  |
| Keyboard shortcuts |  | Shortcut set (TypeEdit or VectorDrive), import of a TeTurboKey.ini, per-command settings |
| Export parameters… |  | Settings (options, theme, shortcuts, ribbon…), tools, templates and themes in one file, for another computer or as a backup |
| Import parameters… |  | Load parameters exported from another computer (whatever is replaced is backed up first) |
| Mouse | F5 | Mouse use (F5): wheel to zoom or scroll, right-click role |
| Plate |  |  |
| Text layout |  | Text lines spread over the plate: number of lines, text volume, automatic margins (each line keeps the plate width as its maximum length) |
| Table |  | Table of cells and texts (rating plates): one line per row, cells separated by “;” |
| Tools |  | Tool table (colours) |

## Help

### VectorDrive

| Command | Shortcut | Purpose |
|---|---|---|
| Commands | F1 | Command and shortcut guide |
| About |  | Version, licences and third-party components |
| Updates |  | Check for a new version |
| What's new |  | What changed in the latest versions (development log, in French) |
| Find a command | Ctrl+K | Find a command by typing a few letters of its name, then Enter |

## Shortcuts without a button

| Command | Shortcut |
|---|---|
| Close tab | Ctrl+F4 |
| Next drawing tab | Ctrl+F6 |
| Previous drawing tab | Ctrl+Shift+F6 |
| Copy with base point | Ctrl+Shift+C |
| Cut with base point | Ctrl+Shift+X |
| Paste at point | Ctrl+Shift+V |
| Colours | Ctrl+8, Ctrl+_ |
| Reference: Top left | Ctrl+Num+7 |
| Reference: Top centre | Ctrl+Num+8 |
| Reference: Top right | Ctrl+Num+9 |
| Reference: Middle left | Ctrl+Num+4 |
| Reference: Centre | Ctrl+Num+5 |
| Reference: Middle right | Ctrl+Num+6 |
| Reference: Bottom left | Ctrl+Num+1 |
| Reference: Bottom centre | Ctrl+Num+2 |
| Reference: Bottom right | Ctrl+Num+3 |
| 2D | Ctrl+1, Ctrl+& |
| 3D | Ctrl+6, Ctrl+- |
| Next layer tab | Ctrl+Tab |
| Previous layer tab | Ctrl+Shift+Tab |
| Reopen the last closed tab | Ctrl+Shift+T |
| Previous mode | Ctrl+D |
| Next mode | Ctrl+F |

