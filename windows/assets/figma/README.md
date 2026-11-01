# Tesla VPN design assets

Source: Figma file `gKL0JdFJt1yzb1DuWeAnyu`, frame `12:3`.
The fixed client canvas is 451 × 852 logical pixels.

- `connection-glow.svg`: unchanged export of node `13:139`, 446 × 446,
  displayed at (2, 215). At runtime its RGB color follows the power button
  (red/amber/green); the original SVG and its alpha gradient stay unchanged.
- `tesla-symbol.svg`: unchanged export of node `1:14`, 111.099 × 73.6882,
  displayed within the power button at (30.2593, 63.0037).
- `Geologica.ttf`: Google Fonts Geologica variable font, bundled under
  `windows/licenses/Geologica-OFL.txt`. Explicit weight/CRSV/SHRP/slnt axes
  preserve the Figma typography in Qt.

SVG files are read locally through Qt's SVG image plugin; no Figma URL or
network request is needed at runtime. Controls keep native Qt input/focus
behavior and the existing connection/import handlers.
