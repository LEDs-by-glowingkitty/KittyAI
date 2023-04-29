import openai
import os
import json
from dotenv import load_dotenv
import prompts
import traceback
import time
load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

# list all functions for the OpenAI AP
default_allowed_tokens = 1000

def get_user_data_filename(user_id):
    return f"{user_id}.json"

def get_user_data(user_id):
    user_file_name = get_user_data_filename(user_id)
    if os.path.exists(user_file_name):
        with open(user_file_name, "r") as f:
            user_data = json.load(f)
    else:
        user_data = {"used_tokens": 0, "allowed_tokens": default_allowed_tokens}

    return user_data

def user_has_permission(user_id):
    user_data = get_user_data(user_id)

    if user_data["used_tokens"] >= user_data["allowed_tokens"]:
        return False
    else:
        return True
    
def update_consumed_tokens(user_id, tokens_used):
    user_file_name = get_user_data_filename(user_id)
    user_data = get_user_data(user_id)

    user_data["used_tokens"] += tokens_used
    user_data["estimated_cost"] = (user_data["used_tokens"] / 1000) * 0.06

    with open(user_file_name, "w") as f:
        json.dump(user_data, f)

def get_thread_name(message, user_id):
    max_retries = 5
    retries = 0
    
    while retries < max_retries:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": "Create a short headline for the user prompt. Always start with a fitting emoji."}, {"role": "user", "content": message}],
                max_tokens=50,
                n=1,
                stop=None,
                temperature=0,
                top_p=1
            )

            assistant_response = response.choices[0].message['content']
            tokens_used = response['usage']['total_tokens']

            update_consumed_tokens(user_id, tokens_used)

            return assistant_response

        except openai.error.RateLimitError as e:
            error_message = (f"Error occurred: {e}")
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
                user_data = {"used_tokens": 0, "allowed_tokens": default_allowed_tokens}

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

            update_consumed_tokens(user_id, tokens_used)

            return assistant_response

        except openai.error.RateLimitError as e:
            error_message = (f"Error occurred: {e}")
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