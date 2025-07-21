import logging
import sys

from config import settings
from exceptions import ImageException
from fastapi import Depends, FastAPI, Path, Request, status
from fastapi.responses import JSONResponse
from service import ImageService, get_image_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

app = FastAPI()


@app.get("/image/profile={width}/{img_url:path}")
async def process_request(
    width: int = Path(..., ge=200, le=2560),
    img_url: str = Path(..., regex=r"(?i).+\.(jpg|jpeg|png|gif|webp|avif)$"),
    image_service: ImageService = Depends(get_image_service),
):
    if settings.MODE == "cache":
        return await image_service.get_processed_image_file()
    return await image_service.get_processed_image_data()


@app.exception_handler(ImageException)
def exception_handler(request: Request, exc: ImageException):
    """
    Returns 500 errors, with details.
    """
    logging.error(f"Error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )
