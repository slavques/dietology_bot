import os
import sys
from pathlib import Path

from PIL import Image, UnidentifiedImageError

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.handlers import goals  # noqa: E402


def test_load_goal_body_fat_photo_falls_back_to_pillow(monkeypatch, tmp_path):
    image_path = tmp_path / "goal_body_fat.png"
    Image.new("RGB", (10, 10), color="red").save(image_path, format="PNG")

    monkeypatch.setattr(goals, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(goals, "GOAL_BODY_FAT_IMAGE_NAME", image_path.name)
    monkeypatch.setattr(goals.imghdr, "what", lambda *_, **__: None)

    result = goals._load_goal_body_fat_photo()

    assert result is not None
    buffered_file, returned_path = result
    assert returned_path == image_path
    assert buffered_file.filename.endswith(".png")
    assert buffered_file.data


def test_load_goal_body_fat_photo_uses_extension_when_pillow_fails(monkeypatch, tmp_path):
    image_path = tmp_path / "goal_body_fat.png"
    Image.new("RGB", (10, 10), color="blue").save(image_path, format="PNG")

    monkeypatch.setattr(goals, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(goals, "GOAL_BODY_FAT_IMAGE_NAME", image_path.name)
    monkeypatch.setattr(goals.imghdr, "what", lambda *_, **__: None)

    def raise_unidentified(*_args, **_kwargs):
        raise UnidentifiedImageError("cannot identify image")

    monkeypatch.setattr(goals.Image, "open", raise_unidentified)

    result = goals._load_goal_body_fat_photo()

    assert result is not None
    buffered_file, returned_path = result
    assert returned_path == image_path
    assert buffered_file.filename.endswith(".png")
    assert buffered_file.data
