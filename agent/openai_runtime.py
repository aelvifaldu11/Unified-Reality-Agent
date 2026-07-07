import json
from openai import OpenAI

class OpenAIRuntime:
    """
    Wrapper around OpenAI API.
    Keeps LLM logic separate from agents.
    """

    def __init__(self, secrets):
        self.api_key = secrets.secrets.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY missing in .env file")

        self.client = OpenAI(api_key=self.api_key)

    def generate_text(self, prompt: str):
        """
        Sends prompt to OpenAI's GPT model and returns JSON-safe output.
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.choices[0].message.content.strip()

            # Try converting into JSON (if LLM returns dict text)
            try:
                return json.loads(text)
            except:
                return {"raw_response": text}

        except Exception as e:
            return {"error": str(e)}
