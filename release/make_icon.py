"""Create the Windows .ico from the tracked SVG source during builds."""
from __future__ import annotations
import sys
from pathlib import Path

from PIL import Image, ImageDraw

target = Path(sys.argv[2])
image = Image.new("RGBA", (256, 256), "#121826")
draw = ImageDraw.Draw(image)
draw.ellipse((42, 42, 214, 214), fill="#4dd6ff")
draw.rounded_rectangle((100, 62, 156, 164), radius=24, outline="#eef6ff", width=15)
draw.arc((74, 110, 182, 198), 0, 180, fill="#eef6ff", width=15)
draw.line((128, 198, 128, 224), fill="#eef6ff", width=15)
image.save(target, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (128, 128), (256, 256)])
