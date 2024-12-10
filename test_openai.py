from openai import OpenAI
import os

# Instantiate the OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")  # This can be omitted if the environment variable is set
)

try:
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Tell me a joke."}
        ],
        max_tokens=50,
        temperature=0.7,
    )
    print(response.choices[0].message.content)
except Exception as e:
    print(f"An error occurred: {e}")