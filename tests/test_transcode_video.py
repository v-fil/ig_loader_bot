"""Phase 4: transcode_video integration tests (need real ffmpeg/ffprobe)."""
import shutil
import subprocess

import pytest

import strategies.utils as utils
from strategies.utils import _ffprobe_duration, transcode_video

pytestmark = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="requires ffmpeg and ffprobe",
)


@pytest.fixture(scope="module")
def noisy_clip(tmp_path_factory) -> bytes:
    """2s of random noise: nearly incompressible, so the source encodes large
    enough to stay well above the (monkeypatched) transcode target."""
    path = tmp_path_factory.mktemp("clips") / "src.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "nullsrc=s=320x240:r=10:d=2,geq=random(1)*255:128:128",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            str(path),
        ],
        check=True, capture_output=True,
    )
    return path.read_bytes()


async def test_transcode_shrinks_video_and_output_is_parseable(noisy_clip, monkeypatch, tmp_path):
    monkeypatch.setattr(utils, "TRANSCODE_TARGET", 100_000)

    result = await transcode_video(noisy_clip)

    assert result is not None
    assert len(result) < len(noisy_clip)
    out = tmp_path / "out.mp4"
    out.write_bytes(result)
    duration = await _ffprobe_duration(str(out))
    assert duration == pytest.approx(2.0, abs=0.5)


async def test_unparseable_input_returns_none():
    assert await transcode_video(b"this is not a video") is None


async def test_result_still_over_limit_returns_none(noisy_clip, monkeypatch):
    monkeypatch.setattr(utils, "TRANSCODE_TARGET", 100_000)
    # ~270 kbit/s for 2s comes out around 70 KB, far above a 1 KB "limit"
    monkeypatch.setattr(utils, "TG_SIZE_LIMIT", 1_000)

    assert await transcode_video(noisy_clip) is None
