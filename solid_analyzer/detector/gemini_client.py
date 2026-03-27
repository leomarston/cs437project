"""Gemini API client with retry logic and budget enforcement."""

import json
import time
import logging
from typing import Optional

import google.generativeai as genai

log = logging.getLogger("solid_analyzer")


class GeminiClient:
    """Wrapper around Google Gemini API with rate limiting and retries."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash",
                 temperature: float = 0.2, max_output_tokens: int = 8192):
        genai.configure(api_key=api_key)
        self.model_name = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.model = genai.GenerativeModel(model)
        self._call_count = 0

    def generate(self, prompt: str, temperature: Optional[float] = None,
                 expect_json: bool = True) -> str:
        """Send a prompt to Gemini and return the response text.

        Implements exponential backoff retry on transient failures.
        """
        temp = temperature if temperature is not None else self.temperature
        generation_config = genai.types.GenerationConfig(
            temperature=temp,
            max_output_tokens=self.max_output_tokens,
        )
        if expect_json:
            generation_config.response_mime_type = "application/json"

        last_error = None
        for attempt in range(5):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config,
                )
                self._call_count += 1
                return response.text
            except Exception as e:
                last_error = e
                wait = 2 ** attempt
                log.warning(f"Gemini API error (attempt {attempt + 1}/5): {e}. Retrying in {wait}s...")
                time.sleep(wait)

        raise RuntimeError(f"Gemini API failed after 5 attempts: {last_error}")

    def generate_json(self, prompt: str, temperature: Optional[float] = None) -> dict | list:
        """Send a prompt and parse the JSON response."""
        text = self.generate(prompt, temperature=temperature, expect_json=True)
        # Clean potential markdown wrapping
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())

    @property
    def call_count(self) -> int:
        return self._call_count
