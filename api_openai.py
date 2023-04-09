import openai
import os
import json
from dotenv import load_dotenv
import prompts
import traceback
import time
load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

# list all functions for the OpenAI API

def get_gpt4_response(messages, temperature,user_id):
    max_retries = 5
    retries = 0
    while retries < max_retries:
        try:
            user_file = f"{user_id}.json"

            if os.path.exists(user_file):
                with open(user_file, "r") as f:
                    user_data = json.load(f)
            else:
                return "Sorry, it seems you don't have an active subscription."

            if user_data["used_tokens"] >= user_data["allowed_tokens"]:
                return "Sorry, your monthly token limit is reached."

            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=messages,
                max_tokens=3000,
                n=1,
                stop=None,
                temperature=temperature,
                top_p=1
            )

            assistant_response = response.choices[0].message['content']
            tokens_used = response['usage']['total_tokens']

            user_data["used_tokens"] += tokens_used
            user_data["estimated_cost"] = (user_data["used_tokens"]/ 1000) * 0.06

            with open(user_file, "w") as f:
                json.dump(user_data, f)

            return assistant_response

        except openai.error.RateLimitError as e:
            error_message = f"Error occurred: {type(e).name}: {str(e)}"
            print(error_message)
            retries += 1
            if retries == max_retries:
                return error_message
            time.sleep(5)

        except Exception as e:
            error_message = (f"Error occurred: {e}")
            print(error_message)
            traceback.print_exc()
            return error_message