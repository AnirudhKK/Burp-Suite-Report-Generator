"""Draws the app icon (a shield with a check mark) as a multi-size .ico. Needs Pillow."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("icon.ico"))
S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
# shield outline: flat top with rounded shoulders, pointed bottom
shield = [
    (512, 70),
    (880, 210),
    (880, 500),
    (850, 650),
    (760, 790),
    (512, 960),
    (264, 790),
    (174, 650),
    (144, 500),
    (144, 210),
]
d.polygon(shield, fill=(31, 58, 95, 255))
inner = [
    (512, 140),
    (810, 255),
    (810, 495),
    (785, 625),
    (705, 745),
    (512, 880),
    (319, 745),
    (239, 625),
    (214, 495),
    (214, 255),
]
d.polygon(inner, fill=(46, 92, 150, 255))
d.line([(350, 520), (470, 640), (690, 400)], fill=(255, 255, 255, 255), width=90, joint="curve")
for x, y in ((350, 520), (470, 640), (690, 400)):
    d.ellipse([x - 45, y - 45, x + 45, y + 45], fill=(255, 255, 255, 255))
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(out)
