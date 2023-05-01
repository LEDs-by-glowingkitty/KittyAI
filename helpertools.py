import aiohttp
import re
from datetime import datetime
import pytz
from geopy.geocoders import Nominatim
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder


async def download_file(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()
            
####################
## Time functions
####################

def location_to_timezone(location_string):
    geolocator = Nominatim(user_agent="geoapiExercises")
    location = geolocator.geocode(location_string)
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lng=location.longitude, lat=location.latitude)
    return timezone_str

def current_time_in_timezone(timezone_str):
    timezone = pytz.timezone(timezone_str)
    current_time = datetime.now(timezone)
    return current_time


def get_date_time_location(location, timezone=None):
    # take location and output time and location
    # input: Berlin Kreuzberg, Germany
    # output: Now is April 30 2023, 8:02PM. In Berlin Kreuzberg, Germany.
    if timezone is None:
        timezone = location_to_timezone(location)
    
    current_time = current_time_in_timezone(timezone)

    # prepare string
    date_string = current_time.strftime("%B %d %Y, %I:%M%p")
    location_string = location
    return f"Now is {date_string}. In {location_string}."


####################

def number_to_word(num):
    num_to_word_dict = {
        1: "one",
        2: "two",
        3: "three",
        4: "four",
        5: "five",
        6: "six",
        7: "seven",
        8: "eight",
        9: "nine",
        10: "ten"
    }
    return num_to_word_dict.get(num, "?")

def split_text(text, max_length):
        sentences = re.split(r'(?<=[.!?])\s+', text)
        message_parts = []
        current_part = ""
        for sentence in sentences:
            if len(current_part) + len(sentence) < max_length:
                current_part += sentence
            else:
                message_parts.append(current_part)
                current_part = sentence
        message_parts.append(current_part)
        return message_parts
    
# Split the message if it's too long for the Discord message limit
def split_message(message, max_length):
    if len(message) < max_length:
        return [message]

    if "```" not in message:
        return split_text(message, max_length)

    message_parts = []
    code_block_pattern = r'(```(?:[a-zA-Z]+\n)?[\s\S]*?```)'
    text_and_code_blocks = re.split(code_block_pattern, message)

    for i, part in enumerate(text_and_code_blocks):
        if i % 2 == 0:  # Text part
            if len(part) > max_length:
                message_parts.extend(split_text(part, max_length))
            elif part.strip():
                message_parts.append(part)
        else:  # Code block part
            match = re.match(r'(```[a-zA-Z]*\n)', part)
            code_block_header = match.group(1) if match else ""
            code_block_content = part[len(code_block_header):-3]

            lines = code_block_content.split('\n')
            current_part = code_block_header
            for line in lines:
                if (len(current_part) + len(line) + 1) < max_length:
                        current_part += line + '\n'
                else:
                    current_part += '```'
                    if current_part != "```":
                        message_parts.append(current_part)
                    current_part = code_block_header + line + '\n'

            current_part += '```'
            message_parts.append(current_part)
    
    message_parts = [item.strip() for item in message_parts if item != ""]
    return message_parts