import os
import time
import logging  # Added for logging
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors

# Configure basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

_client = None


def _get_client():
    global _client
    if _client is None:
        logger.info("Initializing new Gemini client...")
        key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if not key:
            logger.error("GEMINI_API_KEY missing in .env")
            raise RuntimeError("GEMINI_API_KEY missing in .env")
        _client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=180000),  # 180 s per call
        )
        logger.info("Gemini client initialized successfully.")
    return _client


def _clean(name):
    # Strip whitespace and quotes from the input string
    return (name or "").strip().strip('"').strip("'")


def _call(model, contents, schema):
    logger.info(f"Preparing API call for model: {model}")
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        # no temperature: Gemini 3 models want the default
    )
    # only the old preview model needs this setting
    """if model.startswith("gemini-3-flash"):
        logger.info("Applying 'thinking_level=low' config for gemini-3-flash model.")
        config.thinking_config = types.ThinkingConfig(thinking_level="low")"""

    if model.startswith("gemini-3"):
        config.thinking_config = types.ThinkingConfig(thinking_level="low")

    logger.info(f"Executing generate_content for model: {model}...")
    return _get_client().models.generate_content(
        model=model, contents=contents, config=config
    )


def generate_json(prompt, schema, image_bytes=None, mime_type=None):
    """Call Gemini and return a validated Pydantic object of type `schema`."""
    logger.info("Starting generate_json execution.")

    main_model = _clean(os.getenv("GEMINI_MODEL"))
    if not main_model:
        logger.error("GEMINI_MODEL missing in .env")
        raise RuntimeError("GEMINI_MODEL missing in .env")

    logger.info(f"Main model selected: {main_model}")

    contents = []
    if image_bytes:
        logger.info(
            f"Adding image content. MIME type: {mime_type}, Size: {len(image_bytes)} bytes"
        )
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
    else:
        logger.info("No image bytes provided, proceeding with text-only prompt.")

    contents.append(prompt)

    # Optional fallback, only used if GEMINI_FALLBACK_MODEL is set in .env
    models = [main_model]
    fallback = _clean(os.getenv("GEMINI_FALLBACK_MODEL"))
    if fallback:
        logger.info(f"Fallback model detected: {fallback}")
        models.append(fallback)
    else:
        logger.info("No fallback model configured.")

    last_err = None
    for model in models:
        logger.info(f"--- Processing with model: {model} ---")
        for attempt in range(2):  # 2 tries per model
            try:
                logger.info(f"Attempt {attempt + 1} of 2 for model {model}.")
                resp = _call(model, contents, schema)

                logger.info(
                    "API call successful. Validating response against schema..."
                )
                validated_obj = schema.model_validate_json(resp.text)
                logger.info("Validation successful. Returning result.")
                return validated_obj

            except errors.APIError as e:
                last_err = e
                logger.warning(
                    f"APIError encountered on model {model}, attempt {attempt + 1}. Code: {e.code}, Message: {e.message}"
                )

                if e.code in (429, 500, 503, 504):  # temporary: wait and retry
                    sleep_time = min(5 * 2**attempt, 40)  # 5, 10, 20, 40, 40, 40 s
                    logger.info(
                        f"Temporary error detected. Sleeping for {sleep_time} seconds before retry..."
                    )
                    time.sleep(sleep_time)
                    continue

                logger.error(
                    f"Fatal APIError encountered (Code: {e.code}). Raising immediately."
                )
                raise  # real errors (400, 403, 404) show immediately

            except Exception as e:
                # Catch any other unexpected errors (like validation errors or network issues)
                logger.error(f"Unexpected error during execution: {str(e)}")
                raise

    logger.error("All attempts and fallback models exhausted. Raising last error.")
    raise last_err
