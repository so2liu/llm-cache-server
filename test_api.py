import unittest
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()  # This loads the variables from .env file


class TestLLMCacheProxy(unittest.TestCase):
    BASE_URL = "http://localhost:9999"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    def setUp(self):
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.OPENAI_API_KEY}",
        }
        self.payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Hello, how are you?"}],
            "temperature": 0.7,
        }

    def test_chat_completions_endpoint(self):
        response = requests.post(
            f"{self.BASE_URL}/chat/completions",
            headers=self.headers,
            data=json.dumps(self.payload),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("choices", data)
        self.assertGreater(len(data["choices"]), 0)

    def test_cache_chat_completions_endpoint(self):
        # First request
        response1 = requests.post(
            f"{self.BASE_URL}/cache/chat/completions",
            headers=self.headers,
            data=json.dumps(self.payload),
        )

        self.assertEqual(response1.status_code, 200)
        data1 = response1.json()

        # Second request with the same payload
        response2 = requests.post(
            f"{self.BASE_URL}/cache/chat/completions",
            headers=self.headers,
            data=json.dumps(self.payload),
        )

        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()

        # The responses should be identical as the second one should be cached
        self.assertEqual(data1, data2)

    def test_streaming_response(self):
        streaming_payload = self.payload.copy()
        streaming_payload["stream"] = True

        response = requests.post(
            f"{self.BASE_URL}/chat/completions",
            headers=self.headers,
            data=json.dumps(streaming_payload),
            stream=True,
        )

        self.assertEqual(response.status_code, 200)
        content = b""
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                content += chunk

        # Check if the response is in the correct SSE format
        self.assertTrue(content.startswith(b"data: "))
        self.assertTrue(content.endswith(b"data: [DONE]\n\n"))


if __name__ == "__main__":
    unittest.main()
