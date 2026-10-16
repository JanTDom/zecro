import io
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
from backend.app.engine.segmentation import segment_image, SegmentationResult

def test_remote_segmentation_service_mock(tmp_path: Path):
    source_img_path = tmp_path / "test_source.jpg"
    out_img_path = tmp_path / "test_out.png"

    # Create dummy source image
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(source_img_path)

    # Create dummy cutout response (RGBA with circle alpha)
    cutout = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(cutout)
    draw.rectangle([20, 20, 80, 80], fill=(255, 0, 0, 255))
    buf = io.BytesIO()
    cutout.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    mock_resp = MagicMock()
    mock_resp.read.return_value = png_bytes
    mock_resp.headers = {"Content-Type": "image/png"}
    mock_resp.__enter__.return_value = mock_resp

    with patch.dict(os.environ, {"ZECRO_SEGMENTATION_SERVICE_URL": "https://segmentation.internal/api/remove-bg"}):
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            result = segment_image(source_img_path, out_img_path)
            assert result.status == "ready"
            assert result.provider == "remote_service"
            assert out_img_path.exists()
            assert result.contour is not None
            assert len(result.contour) > 0
            assert mock_urlopen.called
