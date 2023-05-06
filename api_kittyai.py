from plugins import api_google as api_google
import core.api_openai as api_openai
import json
import os
import asyncio
from dotenv import load_dotenv, dotenv_values
import helpertools
import re

# this python class is used to process all the messages from the user, check if plugins are requested and calls them if needed

class KittyAIapi:
    def __init__(self,debug=False):
        self.debug = debug
        self.llm_prompt_precise = "You are a helpful assistant called KittyAI. Provide concise and helpful responses."
        self.llm_prompt_creative = "You are a helpful assistant called KittyAI."
        self.llm_prompt_plugins_intro = "Identify if the user asked to execute one or multiple of the following plugins or settings. If so, integrate the python function calls like \"function(parameters)\" in your response."
        self.llm_system_prompt_intro = "If not, follow the instructions and answer the questions. Also always follow the system prompt:"
        self.llm_summarize_history_prompt = "Summarize in concise bullet points what has been said. If you are given user messages, summarize what the user said. If you are given assistant messages, summarize what the assistant said. If you are given both, summarize what the user and the assistant said."
        self.llm_create_thread_name_prompt = "Write a short and precise headline. Always start with a fitting emoji."
        self.available_plugins = [
            "Google Search",
            "Google Image Search",
            "YouTube",
            "Google Maps"
        ]
        self.plugin_functions = {
            "Google Search": "search(query, num_results, page)",
            "Google Image Search": "searchimages(query, num_results, page)",
            "YouTube": "searchvideos(query, num_results, page, regionCode, relevanceLanguage)",
            "Google Maps": "searchlocations(query,where,open_now,num_results,page)"
        }
        self.required_api_keys = {
            "OpenAI": ["OPENAI_API_KEY"],
            "Google Search": ["GOOGLE_API_KEY","GOOGLE_CX_ID"],
            "Google Image Search": ["GOOGLE_API_KEY","GOOGLE_CX_ID"],
            "YouTube": ["GOOGLE_API_KEY"],
            "Google Maps": ["GOOGLE_API_KEY"]
        }
        self.default_user_settings = {
            "location": "Berlin,Germany", # city/country
            "timezone": None,
            "language": "en",
            "llm_default_model": "gpt-4"
        }
        self.default_user_history = {
            "monthly_used_tokens": 0,
            "estimated_monthly_cost_eur": 0.0,
            "past_months_used_tokens": [],
            "past_months_cost_eur": []
        }
        self.default_channel_settings = {
            "location": "Berlin,Germany", # city/country
            "timezone": None,
            "language": "en",
            "llm_systemprompt": self.llm_prompt_precise,
            "llm_creativity": 0.0,
            "llm_default_model": "gpt-4",
            "autorespond": True,
            "num_of_last_messages_included": 5,
            "plugins": self.available_plugins,
            "debug_mode": False
        }
        self.num_results_default = 4
        self.default_user_secrets_folder = "user_secrets"
        self.default_user_history_folder = "user_history"
        self.default_user_settings_folder = "user_settings"
        self.log("KittyAI API initialized")
    
    def log(self,message,failure=False):
        if self.debug or failure:
            if failure:
                print("\033[31m"+message+"\033[0m")
            else:
                print(message)
            print("--------")

    #############################
    ## Process messages
    #############################

    async def split_long_messages(self,message,max_length=2000):
        self.log("split_long_messages(message="+str(message)+",max_length="+str(max_length)+")")
        if len(message) > max_length:
            if "<newmessagestart>" in message:
                split_response = message.split("<newmessagestart>")
                splitter = "<newmessagestart>"
            elif "\n\n\n" in message:
                split_response = message.split("\n\n\n")
                splitter = "\n\n\n"
            elif "\n\n" in message:
                split_response = message.split("\n\n")
                splitter = "\n\n"
            elif "\n" in message:
                split_response = message.split("\n")
                splitter = "\n"
            else:
                split_response = message.split(". ")
                splitter = ". "
            messages = []
            new_message = ""
            for entry in split_response:
                # now build new messages by adding together the strings in r until the length of the string is too long
                # then add the message to the messages list and start a new message
                new_message += entry + splitter
                # this message plus the next one would be too long, add the message to the list and start a new message
                # prevent list index out of range 
                if split_response.index(entry) + 1 < len(split_response) and len(new_message) + len(split_response[split_response.index(entry) + 1]) > max_length:
                    # remove all instances of <newmessagestart> from the new_message
                    messages.append(new_message.replace("<newmessagestart>",""))
                    new_message = ""
            # add the last message to the list
            messages.append(new_message.replace("<newmessagestart>",""))
            return messages
        else:
            return [message]


    async def shorten_message_history(
            self,
            previous_chat_history,
            user_id,
            api_key=None,
            llm_summarize_model="gpt-3.5-turbo",
            llm_summarize_max_tokens=2000,
            max_summary_length=500
            ):
        self.log("shorten_message_history(previous_chat_history="+str(previous_chat_history)+",llm_summarize_model="+llm_summarize_model+",llm_summarize_max_tokens="+str(llm_summarize_max_tokens)+")")
        
        if not previous_chat_history:
            return previous_chat_history
        
        # check if user has api key for OpenAI
        if not api_key:
            api_key = await self.get_api_key(user_id,"OPENAI_API_KEY")
            if not api_key:
                self.log("shorten_message_history(): No OpenAI API key found for user "+user_id,failure=True)
                return previous_chat_history
        
        # Reduce tokens used:
        # shorten all links sent by assistant to only domain and domain extension. example: https://www.youtube.com/watch?v=ZE5zXLOyEOQ -> youtube.com/...
        summarize_this_chat_history = ""
        most_recent_response = None
        
        # loop over history with counter
        # TODO: from the last one backwards to the first one
        for i,entry in enumerate(previous_chat_history):
            try:
                
                if entry["role"] == "assistant":
                    try:
                        entry["content"] = re.sub(r'(https?://)?(www\.)?(?P<domain>[a-zA-Z0-9-]+)\.(?P<extension>[a-zA-Z0-9-]+)(\.[a-zA-Z0-9-]+)?(/.*)?', r'\g<domain>.\g<extension>/...', entry["content"])
                        self.log("shorten_message_history(): shortened links: "+entry["content"])
                    except:
                        self.log("shorten_message_history(): error while shortening links: "+entry["content"],failure=True)
                
                # if the message is not the last one, add it to the full message history string
                if i < len(previous_chat_history)-1:
                    token_length = api_openai.count_tokens(entry["content"])
                    self.log("shorten_message_history(): The message has "+str(token_length)+" tokens: "+entry["content"])
                    if api_openai.count_tokens(summarize_this_chat_history)+token_length <= llm_summarize_max_tokens:
                        summarize_this_chat_history += entry["role"]+": "+entry["content"]+"\n"
                else:
                    # else define it as the most recent message
                    most_recent_response = entry

            except Exception as e:
                self.log("shorten_message_history(): error while shortening message: "+str(e),failure=True)
        
        full_message_history_token_length = api_openai.count_tokens(summarize_this_chat_history)
        self.log("shorten_message_history(): The full history has now "+str(full_message_history_token_length)+" tokens: "+summarize_this_chat_history)
        self.log("shorten_message_history(): Most_recent_response: "+str(most_recent_response))

        # if summarize_this_chat_history is setup, summarize it
        summarized_history = None
        if summarize_this_chat_history:
            summarized_history, used_tokens = await api_openai.get_llm_response(
                key = api_key,
                messages = [
                        {
                            "role":"system",
                            "content":self.llm_summarize_history_prompt
                        },
                        {
                            "role":"assistant",
                            "content":summarize_this_chat_history
                        }
                    ],
                model = llm_summarize_model,
                max_tokens = max_summary_length
            )

            self.log("shorten_message_history(): Summary: \n"+summarized_history)
            self.log("shorten_message_history(): Used tokens (message+response):\n"+str(used_tokens))
            # output how many tokens have been saved by summarizing
            
            cost = api_openai.get_costs(used_tokens,"gpt-3.5-turbo")
            self.log("shorten_message_history(): Cost USD: \n"+str(cost))
        else:
            self.log("shorten_message_history(): No messages to summarize")

        # return summarized history 
        shortened_message_history = [
            {
                "role":"assistant",
                "content":summarized_history
            },
            most_recent_response
        ] if summarized_history else [most_recent_response]

        return shortened_message_history

    async def process_message(
            self,
            channel_id,
            user_id,
            new_message,
            previous_chat_history=[],
            usable_plugins=[],
            llm_main_creativity=None,
            llm_main_model=None,
            llm_summarize_model="gpt-3.5-turbo",
            ):
        self.log("process_message(channel_id="+str(channel_id)+",user_id="+str(user_id)+",new_message="+str(new_message)+",previous_chat_history="+str(previous_chat_history)+")")

        # previous_chat_history (optional) is a list of dictionaries with the following keys: "sender" ("user", or "assistant") and "message".
        # example: [{"sender": "user", "message": "Hello!"}, {"sender": "assistant", "message": "Hi!"}]

        # load channel settings to define creativity and model
        if not llm_main_creativity:
            llm_main_creativity = await self.get_channel_settings(channel_id,"llm_creativity")
            self.log("process_message(): llm_main_creativity="+str(llm_main_creativity))
        if not llm_main_model:
            llm_main_model = await self.get_channel_settings(channel_id,"llm_default_model")
            self.log("process_message(): llm_main_model="+str(llm_main_model))

        # check if user has API keys to use OpenAI using get_api_key
        open_ai_key = await self.get_api_key(user_id,"OPENAI_API_KEY")
        if not open_ai_key:
            # if not, return error message
            message_output = "Error: No OpenAI API key found for your User ID."
            self.log("process_message(): "+message_output,failure=True)
            return message_output

        # add system prompt message to message history before all other messages
        # system_prompt = await self.get_system_prompt(
        #     user_id=user_id,
        #     channel_id=channel_id,
        #     usable_plugins=usable_plugins
        # )
        system_prompt = "You are a helpful assistant. Keep your answers concise."

        self.log("process_message(): system_prompt="+str(system_prompt))

        # shorten history
        message_history = await self.shorten_message_history(
            previous_chat_history=previous_chat_history,
            user_id=user_id,
            api_key=open_ai_key,
            llm_summarize_model=llm_summarize_model
            )
        
        
        message_history.insert(0,{
            "role":"system",
            "content":system_prompt
        })

        # add new message to message history
        message_history.append({
            "role":"user",
            "content":new_message
            })

        self.log("process_message(): message_history="+str(message_history))

        # send message to OpenAI API and get response
        response, used_tokens = await api_openai.get_llm_response(
            key = open_ai_key,
            messages = message_history,
            temperature=llm_main_creativity,
            model = llm_main_model
        )

        # self.log("process_message(): Response: \n"+response)
        # self.log("process_message(): Used model: \n"+llm_main_model)
        # self.log("process_message(): Used tokens (message+response):\n"+str(used_tokens))
        # cost = api_openai.get_costs(used_tokens,"gpt-4")
        # self.log("process_message(): Cost USD: \n"+str(cost))

        # # process response and extract plugin requests
        # response = await self.process_commands(
        #     message=response,
        #     user_id=user_id,
        #     usable_plugins=usable_plugins
        # )

        return response

    async def get_thread_name(self,user_id,message):
        self.log("get_thread_name(message="+message+")")
        # get key from user_id
        open_ai_key = await self.get_api_key(user_id,"OPENAI_API_KEY")
        #  use gpt-3.5-turbo to generate a thread name
        thread_name, tokens_used = await api_openai.get_llm_response(
            key = open_ai_key,
            messages = [
                {
                    "role":"system",
                    "content":self.llm_create_thread_name_prompt
                },
                {
                    "role":"user",
                    "content":message
                }
                ],
                model="gpt-3.5-turbo"
        )
        self.log("get_thread_name(): thread_name="+thread_name)
        self.log("get_thread_name(): tokens_used="+str(tokens_used))
        cost = api_openai.get_costs(tokens_used,"gpt-3.5-turbo")
        self.log("get_thread_name(): Cost USD: \n"+str(cost))
        # return first 100 characters of thread name
        return thread_name[:97]+"..." if len(thread_name) > 100 else thread_name
    
    #############################
    ## Plugins
    #############################

    async def search(
            self,
            google_api_key,
            google_cx_id,
            query,
            num_results=4,
            page=1,
            interpret_output_with_llm_prompt=None
            ):
        try:
            results = await api_google.search(
                google_api_key=google_api_key,
                google_cx_id=google_cx_id,
                query=query,
                num_results=num_results,
                page=page
                )

            # output message with all results and emoji for search
            message_output = "\n:mag: Google search results for\n**\"" + query + "\"**:\n\n"

            # add results with number of the result as emoji and title and link
            for i in range(len(results)):
                message_output += ":" + helpertools.number_to_word(i+1) + ": " + results[i]['title'] + "\n"
                message_output += results[i]['link']

                # add  "\n\n" if not last result
                if i < len(results)-1:
                    message_output += "\n\n"

            return message_output
        
        except Exception as e:
            try:
                error_message = e.error_details[0]['message']
                self.log("Error: " + error_message, True)
                message_output = "Error: " + error_message
                return message_output
            except:
                self.log("Error: " + str(e), True)
                message_output = "Error: " + str(e)
                return message_output
        
        

    async def searchimages(
            self,
            google_api_key,
            google_cx_id,
            query,
            num_results=4,
            page=1,
            interpret_output_with_llm_prompt=None
            ):
        try:
            results = await api_google.searchimages(
                google_api_key=google_api_key,
                google_cx_id=google_cx_id,
                query=query,
                num_results=num_results,
                page=page
                )

            # output message with all results and emoji for images
            message_output = "\n:frame_photo: Google Images for\n**\"" + query + "\"**:\n\n"

            # add results with number of the result as emoji and title and link
            for i in range(len(results)):
                message_output += ":" + helpertools.number_to_word(i+1) + ": " + results[i]['title'] + "\n"
                # add both source and image link and filename
                message_output += "**Source:** <"+results[i]['source'] + ">\n"
                message_output += "**Image:** "+results[i]['image'] + "\n"

                # add  "\n\n" if not last result
                if i < len(results)-1:
                    message_output += "\n\n"
                
            return message_output
        
        except Exception as e:
            try:
                error_message = e.error_details[0]['message']
                self.log("Error: " + error_message, True)
                message_output = "Error: " + error_message
                return message_output
            except:
                self.log("Error: " + str(e), True)
                message_output = "Error: " + str(e)
                return message_output

    async def searchvideos(
            self,
            google_api_key,
            query,
            num_results=4,
            page=1,
            regionCode="US",
            relevanceLanguage="en",
            interpret_output_with_llm_prompt=None
            ):
        try:
            results = await api_google.searchvideos(
                google_api_key=google_api_key,
                query=query,
                num_results=num_results,
                page=page,
                regionCode=regionCode,
                relevanceLanguage=relevanceLanguage
                )
            
            # output message with all results and emoji for videos
            message_output = "\n:movie_camera: YouTube videos for\n**\"" + query + "\"**:\n\n"

            # add results with number of the result as emoji
            for i in range(len(results)):
                message_output += ":" + helpertools.number_to_word(i+1) + ": " + results[i]['title'] + "\n"
                message_output += results[i]['link'] + "\n"

                # add  "\n\n" if not last result
                if i < len(results)-1:
                    message_output += "\n\n"

            return message_output
        
        except Exception as e:
            try:
                error_message = e.error_details[0]['message']
                self.log("Error: " + error_message, True)
                message_output = "Error: " + error_message
                return message_output
            except:
                self.log("Error: " + str(e), True)
                message_output = "Error: " + str(e)
                return message_output
    
    async def searchlocations(
            self,
            google_api_key,
            query,
            where=None,
            open_now=False,
            num_results=4,
            page=1,
            interpret_output_with_llm_prompt=None
            ):
        try:
            results = await api_google.searchlocations(
                google_api_key=google_api_key,
                query=query,
                where=where,
                open_now=open_now,
                num_results=num_results,
                page=page)
            
            # output message with all results and emoji for locations
            message_output = "\n:round_pushpin: Locations for\n**\"" + query + "\"**:\n\n"

            # add results with link to google maps with number of the result as emoji
            for i in range(len(results)):
                message_output += ":" + helpertools.number_to_word(i+1) + ": " + results[i]['title'] + "\n"
                message_output += results[i]['link']

                # add  "\n\n" if not last result
                if i < len(results)-1:
                    message_output += "\n\n"
            
            return message_output
        
        except Exception as e:
            try:
                error_message = e.error_details[0]['message']
                self.log("Error: " + error_message, True)
                message_output = "Error: " + error_message
                return message_output
            except:
                self.log("Error: " + str(e), True)
                message_output = "Error: " + str(e)
                return message_output
            
    #############################
    
    #############################
    ## Plugin related functions
    #############################
    
    async def check_plugins_usable(self,user_id,plugins_list):
        # check if all plugins are usable (keys are set)
        # remove every plugin from the list where keys have not been set
        self.log("Checking keys for all plugins: "+str(plugins_list))
        useable_plugins = []
        for plugin in plugins_list:
            self.log("Checking keys for plugin: "+plugin)
            # check if all keys are set for each plugin using get_api_key. If yes, add it to the list of accessible plugins
            key_accessible = True
            for key in self.required_api_keys[plugin]:
                if not await self.get_api_key(user_id,key):
                    key_accessible = False
                    break
            
            if key_accessible:
                useable_plugins.append(plugin)
        
        return useable_plugins
    
    
    async def process_commands(self,message,user_id,usable_plugins=[]):
        # check if the user wants to use a plugin
        self.log("process_commands(message="+message+")")
        if not usable_plugins:
            usable_plugins = await self.check_plugins_usable(user_id,self.available_plugins)
            if usable_plugins:
                self.log("Found usable plugins: "+str(usable_plugins))
            else:
                self.log("No usable plugins found.")

        for plugin in usable_plugins:
            # add the function name to the list of plugin functions, without the parameters. e.g. "searchvideos"
            plugin_text_output = "..."
            found_plugin = False
            try:
                function_name = self.plugin_functions[plugin].split("(")[0]
        
                # check if any of the plugin functions is in the message and extract the function name including variables (e.g. "searchvideos("cats",4,1)")
                pattern = rf'{function_name}\((.*?)\)'
                matches = list(re.finditer(pattern, message))
        
                for match in matches:
                    found_plugin = True
                    params_str = match.group(1)
                    self.log("Found plugin function: " + function_name + " with parameters: " + params_str)
        
                    # Call the function with the extracted parameters and attach all api keys / secrets for the given plugin
                    plugin_secrets = []
                    for key in self.required_api_keys[plugin]:
                        plugin_secrets.append(await self.get_api_key(user_id, key))
        
                    path = "self." + function_name + "(" + ",".join(['"{}"'.format(secret) for secret in plugin_secrets]) + "," + params_str + ")"
                    plugin_text_output = await eval(path)
        
                    # Replace the matched function call with the output of the function
                    message = message.replace(function_name + "(" + params_str + ")", plugin_text_output)
        
            except Exception as e:
                self.log("Error: " + str(e), True)
                plugin_text_output = "Error: " + str(e)

            # if message ends with <newmessagestart> (might also have \n\n behind it), remove <newmessagestart> and everything after it. Using regex
            if message.endswith("<newmessagestart>"):
                message = re.sub(r"<newmessagestart>.*$", "", message)
        
            if found_plugin:
                self.log("Message after plugin function replacement: " + message)
        
        
        return message

    #############################

    #############################
    ## Prompt engineering
    #############################

    
    async def get_system_prompt(self,user_id,channel_id,usable_plugins=[]):
        self.log("get_system_prompt(user_id="+user_id+",channel_id="+channel_id+")")
        # get channel settings for the system prompt and plugins
        channel_settings = await self.get_channel_settings(channel_id,"all")

        # build system prompt:
        
        # + plugin prompt
        # + plugins
        # + system prompt

        prompt = ""
        # Date + Location
        # if channel location is set, get the date and time for that location
        if "location" in channel_settings and channel_settings["location"]:
            # if no timezone set for channel, get it based on the location
            if not "timezone" in channel_settings or not channel_settings["timezone"]:
                channel_settings["timezone"] = await helpertools.location_to_timezone(channel_settings["location"])
                # save the timezone to the channel settings
                await self.update_channel_setting(channel_id,"timezone",channel_settings["timezone"])

            prompt += await helpertools.get_date_time_location(channel_settings["location"],channel_settings["timezone"])+"\n"

        # add all plugins
        # if no plugins defined, use default plugins (all)
        if usable_plugins:
            channel_settings["plugins"] = usable_plugins
        else:
            if not "plugins" in channel_settings:
                channel_settings["plugins"] = self.available_plugins
        
            channel_settings["plugins"] = await self.check_plugins_usable(user_id,channel_settings["plugins"])
        
        # if no plugins set, ignore plugins
        if channel_settings["plugins"]:
            prompt += self.llm_prompt_plugins_intro+"\n\n"
            prompt += "Plugins:\n"
            for plugin in channel_settings["plugins"]:
                # add plugin name and function
                prompt += plugin + " -> " + self.plugin_functions[plugin]+ "\n"
            
            # add num_results
            prompt += "\nnum_results default is " + str(self.num_results_default)+"\n\n"

            prompt += self.llm_system_prompt_intro+" "

        # add system prompt
        # if no llm_systemprompt in channel settings, use default
        if not "llm_systemprompt" in channel_settings or not channel_settings["llm_systemprompt"]:
            # if llm_creativity is set to 0, use precise prompt
            if not "llm_creativity" in channel_settings or channel_settings["llm_creativity"] == 0.0:
                channel_settings["llm_systemprompt"] = self.llm_prompt_precise
            else:
                channel_settings["llm_systemprompt"] = self.llm_prompt_creative

        prompt += channel_settings["llm_systemprompt"]

        return prompt


    ####################
    ## API keys
    ####################

    async def get_api_key(self,user_id,key_type):
        # get the api key from the database
        self.log("get_api_key(user_id="+str(user_id)+",key_type="+str(key_type)+")")
        # generate the path to the .env file with self.default_user_secrets_folder, independent of the operating system
        path = os.path.join(self.default_user_secrets_folder, f"{user_id}.env")
        load_dotenv(path)
        key = os.getenv(str(key_type))
        if key == None:
            self.log("Error: API key not found: "+str(key_type),True)
            return None
        else:
            return key
    
    async def set_api_key(self, user_id, key_type, key):
        # set the api key to the database
        self.log("set_api_key(user_id="+user_id+",key_type="+key_type+",key="+key+")")

        # check if the user has a .env file
        env_file_path = os.path.join("users", f"{user_id}.env")
        if not os.path.exists(env_file_path):
            # create the .env file
            with open(env_file_path, "w") as f:
                f.write(f"{key_type}=\"{key}\"")
            
        else:
            # load the existing .env file
            env_values = dotenv_values(env_file_path)
            env_values[key_type] = key

            # update the .env file with the new key value
            with open(env_file_path, "w") as f:
                for k, v in env_values.items():
                    f.write(f"{k}=\"{v}\"\n")
            self.log("API key saved")

        return True

    async def delete_api_key(self, user_id, key_type):
        # delete the api key from the database
        self.log("delete_api_key(user_id="+user_id+",key_type="+key_type+")")
        # check if the user has a .env file
        env_file_path = os.path.join("users", f"{user_id}.env")
        if os.path.exists(env_file_path):
            # load the existing .env file
            env_values = dotenv_values(env_file_path)
            del env_values[key_type]

            # update the .env file with the new key value
            with open(env_file_path, "w") as f:
                for k, v in env_values.items():
                    f.write(f"{k}=\"{v}\"\n")
            self.log("API key deleted")
        
        return True

    ####################


    ####################
    ## User Settings
    ####################

    async def get_user_settings(self,user_id,setting="all"):
        # check if user_settings/user_id.json exists and load it
        self.log("get_user_settings(user_id="+user_id+",setting="+setting+")")

        # load user settings json
        if os.path.exists(self.default_user_settings_folder+'/'+user_id+'.json'):
            with open(self.default_user_settings_folder+'/'+user_id+'.json') as f:
                user_settings = json.load(f)
                self.log(self.default_user_settings_folder+"/"+user_id+".json:")
                self.log(str(user_settings))

                if setting == "all":
                    return user_settings
                else:
                    # return the setting
                    if setting in user_settings:
                        return user_settings[setting]
                    else:
                        # return default value
                        if setting in self.default_user_settings:
                            return self.default_user_settings[setting]
                        else:
                            self.log("Error: Setting not found in default settings",True)


    ####################
    ## Channel Settings
    ####################
    
    async def get_channel_settings(self,channel_id,setting="all"):
        # get the channel settings from the database
        self.log("get_channel_settings(channel_id="+str(channel_id)+",setting="+str(setting)+")")
        # load channel settings json
        if not os.path.exists('channel_settings.json'):
            default_channel_settings = {"channels":{}}
            with open('channel_settings.json', 'w') as f:
                json.dump(default_channel_settings, f, indent=4)

        with open('channel_settings.json') as f:
            channel_settings = json.load(f)
            self.log("channel_settings.json:")
            self.log(str(channel_settings))

            if str(channel_id) in channel_settings["channels"]:
                if setting == "all":
                    return channel_settings["channels"][str(channel_id)]
                else:
                    # return the setting
                    if setting in channel_settings["channels"][str(channel_id)]:
                        return channel_settings["channels"][str(channel_id)][setting]
                    else:
                        # return default value
                        if setting in self.default_channel_settings:
                            return self.default_channel_settings[setting]
                        else:
                            self.log("Error: Setting not found in default settings",True)
            else:
                # if no custom settings, return default settings
                if setting == "all":
                    return self.default_channel_settings
                else:
                    # return default value
                    if setting in self.default_channel_settings:
                        return self.default_channel_settings[setting]
                    else:
                        self.log("Error: Setting not found in default settings",True)

    
    async def update_channel_setting(self,channel_id,setting,new_value):
        # update the channel settings to the database
        # settings: llm_systemprompt, llm_creativity, autorespond, num_of_last_messages_included, debug_mode
        self.log("update_channel_setting(channel_id="+channel_id+",setting="+setting+",new_value="+new_value+")")

        if os.path.exists('channel_settings.json'):
            with open('channel_settings.json') as f:
                channel_settings = json.load(f)
                self.log("old channel_settings.json:")
                self.log(str(channel_settings))

                # update the channel settings
                if str(channel_id) in channel_settings["channels"]:
                    channel_settings["channels"][str(channel_id)][setting] = new_value
                else:
                    channel_settings["channels"][str(channel_id)] = {}
                    channel_settings["channels"][str(channel_id)][setting] = new_value
        else:
            # create the channel_settings.json file and add the channel settings
            channel_settings = {}
            channel_settings["channels"] = {}
            channel_settings["channels"][str(channel_id)] = {}
            channel_settings["channels"][str(channel_id)][setting] = new_value

        # save the channel settings
        with open('channel_settings.json', 'w') as f:
            json.dump(channel_settings, f, indent=4)
            self.log("saved new channel_settings.json:")
            self.log(str(channel_settings))

    
    async def reset_channel_settings(self,channel_id):
        # reset the channel settings to default
        self.log("reset_channel_settings(channel_id="+channel_id+")")
        
        if os.path.exists('channel_settings.json'):
            with open('channel_settings.json') as f:
                channel_settings = json.load(f)
                self.log("old channel_settings.json:")
                self.log(str(channel_settings))

                # reset the channel settings
                if str(channel_id) in channel_settings["channels"]:
                    # remove the channel settings
                    del channel_settings["channels"][str(channel_id)]
                    # save the channel settings
                    with open('channel_settings.json', 'w') as f:
                        json.dump(channel_settings, f, indent=4)
                        self.log("saved new channel_settings.json:")
                        self.log(str(channel_settings))
                        
                else:
                    self.log("Channel settings not found",True)
        else:
            self.log("Channel settings file not found",True)

    ####################


    ####################
    ## Plugins
    ####################

    async def update_plugins(self,channel_id,plugin,new_status):
        # activate or deactivate a plugin for a channel
        self.log("update_plugins(channel_id="+channel_id+",plugin="+plugin+",new_status="+new_status+")")

        if plugin == "all":

            if new_status == "activate":
                self.log("Activating all plugins")
                await self.update_channel_setting(channel_id,"plugins",self.available_plugins)

            elif new_status == "deactivate":
                self.log("Deactivating all plugins")
                await self.update_channel_setting(channel_id,"plugins",[])

            else:
                self.log("Invalid value. Accepted values are 'activate' and 'deactivate'.",True)
                return False

        else:
            if new_status == "activate":

                self.log("Activate plugin: " + plugin)
                plugins = await self.get_channel_settings(channel_id,"plugins")
                if plugins == None:
                    plugins = []
                if plugin in plugins:
                    self.log("Plugin already activated: " + plugin)
                else:
                    plugins.append(plugin)
                    await self.update_channel_setting(channel_id,"plugins",plugins)
                    self.log("Plugin activated: " + plugin)

            elif new_status == "deactivate":

                self.log("Deactivating plugin: " + plugin)
                plugins = await self.get_channel_settings(channel_id,"plugins")
                if plugins == None:
                    plugins = []
                if plugin in plugins:
                    plugins.remove(plugin)
                    await self.update_channel_setting(channel_id,"plugins",plugins)
                else:
                    self.log("Plugin already deactivated: " + plugin)

            else:
                self.log("Invalid value. Accepted values are 'activate' and 'deactivate'. Received: " + new_status,True)
                return False

    ####################