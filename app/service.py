import asyncio
import logging
import mimetypes
import uuid
from io import BytesIO
from pathlib import Path
from typing import Union

import httpx
import pillow_avif  # noqa
from cachetools import LRUCache
from config import settings
from exceptions import ImageException
from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image

logger = logging.getLogger(__name__)

_locks = LRUCache(maxsize=2000)


def get_lock(key: str):
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]


mimetypes.add_type("image/avif", ".avif")


class ImageService:
    """
    Image processing service: downloading, validation,
    resizing, compression, and saving.

    Attributes:
        MAX_IMAGE_SIZE (int): Maximum allowed image size.
        RESIZE_DIR (Path): Directory for saving processed images.
        QUALITY (int): Quality level for saving images.
        ORIGIN_URL (str): Base URL for downloading original images.
    """

    MAX_IMAGE_SIZE = settings.MAX_IMAGE_SIZE
    RESIZE_DIR = settings.RESIZE_DIR
    QUALITY = settings.QUALITY
    ORIGIN_URL = settings.ORIGIN_URL

    def __init__(self, request: Request, img_url: str, width: int):
        self.request = request
        self.img_url = img_url
        self.width = width
        self._accept_info = None
        self.REQUEST_ID = str(uuid.uuid4())[:8]

    @staticmethod
    def validate_image_data(
            image_data: Union[BytesIO, str], raise_exception=True
    ) -> bool:
        """Checks that the image is valid."""
        try:
            with Image.open(image_data) as img:
                img.verify()
                return True
        except Exception as e:
            if not raise_exception:
                return False
            raise ImageException(str(e))

    def transform_image(self, image_data: BytesIO) -> BytesIO:
        """
        Resizes the image while preserving aspect ratio,
        converts and compresses it.
        """
        fmt = self.get_fmt()
        logger.info(
            f"[{self.REQUEST_ID}] Resizing/Converting: url={self.img_url}, "
            f"width={self.width}, "
            f"fmt={fmt}, "
            f"q={self.QUALITY}"
        )
        with Image.open(image_data) as img:
            orig_width, orig_height = img.size
            height = int(orig_height * self.width / orig_width)
            if fmt is None:
                fmt = img.format
            output_io = BytesIO()
            img.thumbnail((self.width, height))
            img.save(output_io, format=fmt, quality=self.QUALITY)
            output_io.seek(0)
            return output_io

    def save_image(self, image_data: BytesIO, filename: str) -> str:
        """Saves the image to the specified file."""
        logger.info(
            f"[{self.REQUEST_ID}] "
            f"Сохраняем: url={self.img_url}, filename={filename}"
        )
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        with open(filename, "wb") as f:
            f.write(image_data.read())
        return filename

    def check_exists_and_valid(self, filename: str) -> bool:
        """
        Checks whether the file exists and whether the image is valid.
        Corrupted files will be deleted.
        """
        check_filename = Path(filename)
        if not check_filename.exists():
            return False
        if self.validate_image_data(filename, raise_exception=False):
            return True
        check_filename.unlink()
        return False

    def get_info_from_accept_header(self) -> tuple:
        """
        Returns a tuple (mime, ext, fmt) from the Accept header, or None.
        """
        if self._accept_info is not None:
            return self._accept_info
        mime_ext_fmt_map = (
            ("image/avif", ".avif", "AVIF"),
            ("image/webp", ".webp", "WEBP")
        )
        accept_header = self.request.headers.get("accept", "")
        accepted_types = sorted([h.strip() for h in accept_header.split(",")])
        for mime, ext, fmt in mime_ext_fmt_map:
            if mime in accepted_types:
                self._accept_info = mime, ext, fmt
                return self._accept_info
        self._accept_info = None
        return None

    def get_mime_type(self) -> str:
        """
        Returns the MIME type from the Accept header
        or determines it from the URL.
        """
        result = self.get_info_from_accept_header()
        if result is not None:
            mime, ext, fmt = result
            return mime
        return mimetypes.guess_type(self.img_url)[0]

    def get_extension(self) -> str:
        """Returns the file extension from the Accept header, or None."""
        result = self.get_info_from_accept_header()
        if result is not None:
            mime, ext, fmt = result
            return ext
        return None

    def get_fmt(self) -> str:
        """Returns the Pillow format from the Accept header, or None."""
        result = self.get_info_from_accept_header()
        if result is not None:
            mime, ext, fmt = result
            return fmt
        return None

    def get_save_url(self) -> str:
        """Generates the path for saving the image."""
        path = self.RESIZE_DIR / self.img_url
        width = str(self.width)
        extension = self.get_extension() or path.suffix
        return str(path.parent / f"{path.stem}-w{width}{extension}")

    def get_download_url(self) -> str:
        """Constructs the full URL for downloading the image."""
        return f"{self.ORIGIN_URL}{self.img_url}"

    def download_image(self) -> BytesIO:
        """
        Downloads the image, checks its size,
        raises exceptions if necessary.
        """
        download_url = self.get_download_url()
        logger.info(f"[{self.REQUEST_ID}] Загружаем: url={download_url}")
        try:
            with httpx.Client(verify=False) as client:
                with client.stream("GET", download_url) as response:
                    if response.status_code >= 400:
                        response.read()
                        raise ImageException(
                            f"request error: url={download_url}, "
                            f"upstream status code={response.status_code}"
                        )
                    content_length = response.headers.get("Content-Length")
                    if (
                        content_length
                        and int(content_length) > self.MAX_IMAGE_SIZE
                    ):
                        raise ImageException(
                            f"request error: url={download_url}, "
                            f"error=File too large"
                        )
                    total = 0
                    image_data = BytesIO()
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > self.MAX_IMAGE_SIZE:
                            raise ImageException(
                                f"request error: url={download_url}, "
                                f"error=File too large"
                            )
                        image_data.write(chunk)
                    image_data.seek(0)
                    return image_data
        except Exception as e:
            raise ImageException(str(e))

    def process_image_to_file(self, filename: str) -> str:
        """
        The core service logic — downloads, resizes, and saves,
        returns the path (str) of the saved image.
        """
        if self.check_exists_and_valid(filename):
            logger.info(
                f"[{self.REQUEST_ID}] "
                f"Sending the image from local disk: url={self.img_url}, "
                f"file={filename}"
            )
            return filename
        image_data = self.download_image()
        self.validate_image_data(image_data)
        image_data = self.transform_image(image_data)
        saved_image = self.save_image(image_data, filename)
        return saved_image

    def process_image_to_data(self) -> BytesIO:
        """
        The core service logic — downloads, resizes, and saves,
        returns the BytesIO of the saved image.
        """
        image_data = self.download_image()
        self.validate_image_data(image_data)
        image_data = self.transform_image(image_data)
        return image_data

    async def get_processed_image_file(self) -> FileResponse:
        """Returns FileResponse."""
        filename = self.get_save_url()
        async with get_lock(filename):
            result_image_file = await run_in_threadpool(
                self.process_image_to_file, filename
            )
        mime = self.get_mime_type()
        logger.info(
            f"[{self.REQUEST_ID}] "
            "Sending FileResponse: "
            f"url={self.img_url}, file={result_image_file}"
        )
        return FileResponse(result_image_file, media_type=mime)

    async def get_processed_image_data(self) -> StreamingResponse:
        """Returns StreamingResponse."""
        result_image_data = await run_in_threadpool(self.process_image_to_data)
        mime = self.get_mime_type()
        logger.info(
            f"[{self.REQUEST_ID}] Sending StreamingResponse: url={self.img_url}"
        )
        return StreamingResponse(content=result_image_data, media_type=mime)


def get_image_service(
    request: Request, img_url: str, width: int
) -> ImageService:
    """Creates an ImageService instance for the current request."""
    return ImageService(request, img_url, width)
