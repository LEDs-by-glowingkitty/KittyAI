import openai
import os
import json
import traceback
import time
import tiktoken

# list all functions for the OpenAI AP
default_allowed_tokens = 1000

def count_tokens(message, model_name="OpenAI gpt-4"):
    if model_name == "OpenAI gpt-4":
        model_name = "gpt-4"
    elif model_name == "OpenAI gpt-3.5-turbo":
        model_name = "gpt-3.5-turbo"
    encoding = tiktoken.encoding_for_model(model_name)
    return len(encoding.encode(message))

def get_costs(tokens_used, model_name="gpt-4"):
    prices_per_token = {
        "gpt-4": 0.06/1000,
        "gpt-3.5-turbo": 0.002/1000,
    }
    return tokens_used * prices_per_token[model_name]

async def api_key_gpt_4_valid(key):
    try:
        openai.api_key = key
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Respond: Ok"}]
            )
        if response.choices[0].message['content']:
            return True
        else:
            return False
    except Exception as e:
        return False

async def api_key_gpt_3_5_turbo_valid(key):
    try:
        openai.api_key = key
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Respond: Ok"}]
            )
        if response.choices[0].message['content']:
            return True
        else:
            return False
    except Exception as e:
        return False

async def get_llm_response(key, messages, temperature=0.0,model="OpenAI gpt-4",max_tokens=3000):
    openai.api_key = key
    max_retries = 5
    retries = 0

    if model == "OpenAI gpt-4" or model == "gpt-4":
        model = "gpt-4"
    else:
        model = "gpt-3.5-turbo"

    while retries < max_retries:
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True if model == "gpt-4" else False
            )

            if model == "gpt-4":
                return response, 0
            else:
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