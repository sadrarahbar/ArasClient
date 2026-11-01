Tesla VPN Android design assets
==============================
Figma file gKL0JdFJt1yzb1DuWeAnyu, frame 15:183 (451 x 852).

connection-glow.svg / connection-glow.png: original SVG and rendered PNG
exports of layer 15:184, intrinsic size 446 x 446. The PNG is used because
Android's SVG shader interpolates this gradient differently from Figma.
A runtime color matrix maps red to the animated button color while retaining
the exported falloff, background and alpha. Source assets stay unchanged.
Display slot: (2, 203), 446 x 446 design units.

tesla-symbol.svg: unchanged SVG export of layer 15:203, intrinsic size
150.081 x 99.5438. Displayed within the 231 x 231 power button at
(40.8766, 85.1103); the button is at (109.5, 316.5).
The title starts at (79, 92.5), status at (118.5, 564.5), and connectivity
button at (127.5, 605.5), following the enlarged-button frame revision.

The full frame uniformly scales to the available safe area of the device.
All assets load locally and require no Figma connection at runtime.

Geologica static fonts in res/font were instantiated from Google Fonts'
Geologica variable font with wght=300/400/500/700 and CRSV=SHRP=slnt=0.
Static instances support Android 7.0/7.1 as well as newer Android releases.
License: assets/licenses/Geologica-OFL.txt.
