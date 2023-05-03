import openai
import os
import json
from dotenv import load_dotenv
import traceback
import time
load_dotenv()
import tiktoken

# list all functions for the OpenAI AP
default_allowed_tokens = 1000

def count_tokens(message, model_name="gpt-4"):
    encoding = tiktoken.encoding_for_model(model_name)
    return len(encoding.encode(message))

def get_costs(tokens_used, model_name="gpt-4"):
    prices_per_token = {
        "gpt-4": 0.06/1000,
        "gpt-3.5-turbo": 0.002/1000,
    }
    return tokens_used * prices_per_token[model_name]

def get_thread_name(message, user_id):
    max_retries = 5
    retries = 0
    
    while retries < max_retries:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": "Create a short headline for the user prompt. Always start with a fitting emoji. Always less then 100 characters in length."}, {"role": "user", "content": message}],
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

async def get_llm_response(key, messages, temperature=0.0,model="gpt-4",max_tokens=3000):
    openai.api_key = key
    max_retries = 5
    retries = 0

    while retries < max_retries:
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            assistant_response = response.choices[0].message['content']
            tokens_used = response['usage']['total_tokens']

            return assistant_response, tokens_used

        except openai.error.RateLimitError as e:
            error_message = (f"Error occurred: {e}")
            print(error_message)
            retries += 1
            if retries == max_retries:
                return error_message, 0
            time.sleep(5)

        except Exception as e:
            error_message = (f"Error occurred: {e}")
            print(error_message)
            traceback.print_exc()
            return error_message, 0