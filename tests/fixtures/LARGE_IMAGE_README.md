# Large test image

The 10000x10000 image_large.png is NOT committed to git (too large).
Generate it locally with:

```python
from PIL import Image
Image.new('RGB', (10000, 10000), (128, 128, 128)).save('image_large.png')
```
