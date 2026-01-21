# Extension Icons

This folder should contain the following icon files:

- `icon16.png` - 16x16 pixels
- `icon48.png` - 48x48 pixels
- `icon128.png` - 128x128 pixels

## Creating Icons

You can create these icons using any image editor. The recommended design:

1. Use a gradient background (purple #667eea to #764ba2)
2. Add a white map pin or location icon
3. Save in PNG format with transparency

## Quick Placeholder

For testing, you can use simple colored squares. Here's how to create them with Python:

```python
from PIL import Image

for size in [16, 48, 128]:
    img = Image.new('RGB', (size, size), color='#667eea')
    img.save(f'icon{size}.png')
```

Or use any online icon generator to create map-related icons.
