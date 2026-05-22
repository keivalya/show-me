import json
import logging
from google.genai import Client
from google.genai.types import Content, Part

logger = logging.getLogger(__name__)

class DirectorAgent:
    def __init__(self, client: Client):
        self.client = client
        with open("prompts/director.txt", "r") as f:
            self.prompt_template = f.read()

    async def route(self, identifier_data, youtube_results=None, procedure_db_match=None):
        """
        identifier_data: {make, model, symptom, ...}
        youtube_results: Optional search results
        procedure_db_match: Optional verified procedure
        """
        logger.info("Running Director Agent")
        
        input_data = {
            "identifier": identifier_data,
            "youtube_results": youtube_results,
            "procedure_db": procedure_db_match
        }

        parts = [Part.from_text(text=self.prompt_template)]
        parts.append(Part.from_text(text=f"Input Data: {json.dumps(input_data)}"))

        response = await self.client.aio.models.generate_content(
            model="gemini-2.5-pro",
            contents=[Content(role="user", parts=parts)],
            config={"response_mime_type": "application/json"}
        )

        try:
            result = json.loads(response.text)
            logger.info(f"Director decision: {result['path']}")
            return result
        except Exception as e:
            logger.error(f"Failed to parse Director response: {e}")
            return {
                "path": "escalate",
                "user_message": "I'm having trouble deciding how to help safely. Let me look into that."
            }
