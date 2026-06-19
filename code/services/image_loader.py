"""
Image loading service.

Reads image files from disk and encodes them as base64 strings
suitable for inline submission to Gemini's vision API.
No business logic; pure I/O.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from config import IMAGE_MIME_TYPE, DATASET_DIR


# ── Types ─────────────────────────────────────────────────────────────────────

class EncodedImage:
    """
    Holds a single image ready for submission to Gemini.

    Attributes:
        image_id:   Filename stem (e.g. "img_1"), used as the canonical ID in output.
        path:       Absolute path to the image file on disk.
        mime_type:  MIME type string (e.g. "image/jpeg").
        b64_data:   Raw base64-encoded bytes of the image file.
    """

    __slots__ = ("image_id", "path", "mime_type", "b64_data")

    def __init__(self, image_id: str, path: Path, mime_type: str, b64_data: str) -> None:
        self.image_id = image_id
        self.path = path
        self.mime_type = mime_type
        self.b64_data = b64_data

    def __repr__(self) -> str:
        return f"EncodedImage(image_id={self.image_id!r}, path={self.path})"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_image_path(relative_path: str, dataset_dir: Path) -> Path:
    """
    Resolve an image path from the CSV to an absolute filesystem path.

    Paths in the CSV are relative to the dataset directory, e.g.:
        images/test/case_001/img_1.jpg

    Args:
        relative_path: Path string as stored in the CSV.
        dataset_dir:   Absolute path to the dataset/ directory.

    Returns:
        Resolved absolute Path.
    """
    return (dataset_dir / relative_path).resolve()


def _image_id_from_path(path: Path) -> str:
    """Return the image ID (filename without extension) from a Path."""
    return path.stem


def _encode_image(path: Path) -> str:
    """
    Read an image file and return its base64-encoded content as a string.

    Args:
        path: Absolute path to the image file.

    Returns:
        Base64-encoded string of the file bytes.

    Raises:
        FileNotFoundError: If the image file does not exist.
        OSError: On other read errors.
    """
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    with path.open("rb") as fh:
        return base64.b64encode(fh.read()).decode("utf-8")


def _mime_type_for_path(path: Path) -> str:
    """
    Return the MIME type for an image based on its file extension.

    Falls back to the configured default if the extension is unrecognised.

    Args:
        path: Path to the image file.

    Returns:
        MIME type string.
    """
    ext_map: dict[str, str] = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return ext_map.get(path.suffix.lower(), IMAGE_MIME_TYPE)


# ── Public API ────────────────────────────────────────────────────────────────

def load_images(
    image_paths: list[str],
    dataset_dir: Path = DATASET_DIR,
) -> list[EncodedImage]:
    """
    Load and base64-encode all images for a single claim.

    Skips missing files with a warning rather than raising, so a partial
    image set can still be assessed. The caller receives only images that
    were successfully read.

    Args:
        image_paths: List of relative image path strings from the CSV.
        dataset_dir: Root directory against which paths are resolved.

    Returns:
        List of EncodedImage objects in the same order as image_paths,
        excluding any that could not be read.
    """
    encoded: list[EncodedImage] = []

    for relative_path in image_paths:
        abs_path = _resolve_image_path(relative_path.strip(), dataset_dir)
        image_id = _image_id_from_path(abs_path)
        mime_type = _mime_type_for_path(abs_path)

        try:
            b64_data = _encode_image(abs_path)
        except (FileNotFoundError, OSError) as exc:
            # Warn and continue; missing images are handled by the rule engine.
            import warnings
            warnings.warn(f"Skipping image {relative_path!r}: {exc}", stacklevel=2)
            continue

        encoded.append(EncodedImage(
            image_id=image_id,
            path=abs_path,
            mime_type=mime_type,
            b64_data=b64_data,
        ))

    return encoded


def image_ids_from_paths(image_paths: list[str]) -> list[str]:
    """
    Derive image IDs from a list of path strings without reading the files.

    Useful for constructing prompts when the actual bytes are not needed yet.

    Args:
        image_paths: List of relative image path strings.

    Returns:
        List of image ID strings (filename stems).
    """
    return [
        os.path.splitext(os.path.basename(p.strip()))[0]
        for p in image_paths
    ]