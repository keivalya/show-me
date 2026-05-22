import json
import logging
from google.genai import Client
from google.genai.types import Content, Part

logger = logging.getLogger(__name__)

class IdentifierAgent:
    def __init__(self, client: Client):
        self.client = client
        with open("prompts/identifier.txt", "r") as f:
            self.prompt_template = f.read()

    async def identify(self, frames_base64, user_text):
        """
        frames_base64: List of base64-decoded JPEG frame bytes
        user_text: Transcribed user audio
        """
        logger.info("Running Identifier Agent")

        parts = [Part.from_text(text=self.prompt_template)]
        parts.append(Part.from_text(text=f"User Spoken Prompt: {user_text}"))

        for frame in frames_base64:
            parts.append(Part.from_bytes(data=frame, mime_type="image/jpeg"))

        response = await self.client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[Content(role="user", parts=parts)],
            config={"response_mime_type": "application/json"}
        )

        try:
            result = json.loads(response.text)
            logger.info(f"Identification result: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to parse Identifier response: {e}")
            return {
                "appliance_category": "unknown",
                "make": "unknown",
                "model": "unknown",
                "symptom": user_text,
                "confidence": 0.0
            }
