"""Gemini API client using REST API with retry logic and budget enforcement."""

import json
import time
import logging
import os
from typing import Optional

import requests

log = logging.getLogger("solid_analyzer")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiClient:
    """Wrapper around Google Gemini REST API with rate limiting and retries."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash",
                 temperature: float = 0.2, max_output_tokens: int = 8192):
        self.api_key = api_key
        self.model_name = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self._call_count = 0

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY not set. Set it via environment variable or config."
            )

    def _build_url(self) -> str:
        return GEMINI_API_URL.format(model=self.model_name) + f"?key={self.api_key}"

    def generate(self, prompt: str, temperature: Optional[float] = None,
                 expect_json: bool = True) -> str:
        """Send a prompt to Gemini and return the response text.

        Implements exponential backoff retry on transient failures.
        """
        temp = temperature if temperature is not None else self.temperature

        generation_config = {
            "temperature": temp,
            "maxOutputTokens": self.max_output_tokens,
        }
        if expect_json:
            generation_config["responseMimeType"] = "application/json"

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": generation_config,
        }

        url = self._build_url()
        last_error = None

        for attempt in range(5):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=120,
                )

                if response.status_code == 200:
                    data = response.json()
                    self._call_count += 1
                    try:
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        return text
                    except (KeyError, IndexError) as e:
                        # Check for safety blocks or empty responses
                        if "candidates" in data and data["candidates"]:
                            finish_reason = data["candidates"][0].get("finishReason", "")
                            if finish_reason == "SAFETY":
                                log.warning("Response blocked by safety filters")
                                return "[]"
                        log.warning(f"Unexpected response structure: {json.dumps(data)[:300]}")
                        return "[]"

                elif response.status_code == 429:
                    # Rate limited
                    wait = 2 ** (attempt + 1)
                    log.warning(f"Rate limited. Waiting {wait}s...")
                    time.sleep(wait)
                    continue

                elif response.status_code >= 500:
                    # Server error, retry
                    wait = 2 ** attempt
                    log.warning(f"Server error {response.status_code}. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                else:
                    error_msg = response.text[:500]
                    raise RuntimeError(
                        f"Gemini API error {response.status_code}: {error_msg}"
                    )

            except requests.exceptions.Timeout:
                last_error = "Request timed out"
                wait = 2 ** attempt
                log.warning(f"Timeout (attempt {attempt + 1}/5). Retrying in {wait}s...")
                time.sleep(wait)

            except requests.exceptions.ConnectionError as e:
                last_error = str(e)
                wait = 2 ** attempt
                log.warning(f"Connection error (attempt {attempt + 1}/5): {e}. Retrying in {wait}s...")
                time.sleep(wait)

            except RuntimeError:
                raise

            except Exception as e:
                last_error = str(e)
                wait = 2 ** attempt
                log.warning(f"Error (attempt {attempt + 1}/5): {e}. Retrying in {wait}s...")
                time.sleep(wait)

        raise RuntimeError(f"Gemini API failed after 5 attempts: {last_error}")

    def generate_json(self, prompt: str, temperature: Optional[float] = None) -> dict | list:
        """Send a prompt and parse the JSON response."""
        text = self.generate(prompt, temperature=temperature, expect_json=True)
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        if not text:
            return []
        return json.loads(text)

    @property
    def call_count(self) -> int:
        return self._call_count
