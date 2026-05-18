import numpy as np
from PIL import Image

from app.pipeline.preprocess import preprocess_image


def _checkerboard(size: int = 200) -> Image.Image:
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    arr[::20, :, :] = 255
    return Image.fromarray(arr)


def test_noop_when_both_off():
    img = _checkerboard()
    out = preprocess_image(img, deskew=False, denoise=False)
    assert out.size == img.size
    assert np.array_equal(np.array(out), np.array(img))


def test_returns_pil_image():
    img = _checkerboard()
    out = preprocess_image(img, deskew=True, denoise=True)
    assert isinstance(out, Image.Image)
    assert out.size == img.size
