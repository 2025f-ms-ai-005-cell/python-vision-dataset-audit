"""Generate original synthetic fixtures, never overwrite a directory."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path('demo-input')
root.mkdir(exist_ok=False)
for split in ('train', 'test'):
    (root/split).mkdir()
image = Image.new('RGB', (960, 540), '#19233b')
draw = ImageDraw.Draw(image)
draw.rectangle((120, 140, 330, 380), fill='#8be0b4')
draw.ellipse((520, 120, 800, 400), fill='#ffbb70')
image.save(root/'train/scene.png')
(root/'test/duplicate.png').write_bytes((root/'train/scene.png').read_bytes())
Image.new('RGB', (32, 32), '#ffbb70').save(root/'train/small.png')
Image.new('RGB', (800, 600), '#8b99e0').save(root/'test/valid.png')
(root/'test/broken.png').write_bytes(b'intentionally corrupt synthetic fixture')
print('Created 5 original synthetic fixtures in demo-input')
