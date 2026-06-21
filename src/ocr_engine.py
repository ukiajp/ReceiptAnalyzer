import logging
import time

from google.cloud import vision


logger = logging.getLogger(__name__)


def extract_text(image_bytes: bytes) -> tuple[str, float]:
    start_time = time.time()

    try:
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_bytes)
        response = client.text_detection(image=image)
        texts = response.text_annotations

        if response.error.message:
            raise Exception(f"Google Vision API error: {response.error.message}")

        if not texts:
            raise Exception("No text detected in image")

        full_text = texts[0].description
        elapsed = time.time() - start_time

        logger.info("OCR completed in %.2f seconds", elapsed)
        return full_text, elapsed
    except Exception as exc:
        logger.error("OCR failed: %s", exc, exc_info=True)
        raise Exception(str(exc)) from exc
