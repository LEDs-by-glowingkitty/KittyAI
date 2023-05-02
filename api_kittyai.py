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
        self.gpt_prompt_precise = "You are a helpful assistant called KittyAI. Provide concise and helpful responses."
        self.gpt_prompt_creative = "You are a helpful assistant called KittyAI."
        self.gpt_prompt_plugins_intro = "Identify if the user asked to execute one or multiple of the following plugins or settings. If so, integrate the python function calls like \"function(parameters)\" in your response."
        self.gpt_system_prompt_intro = "If not, follow the instructions and answer the questions. Also always follow the system prompt:"
        self.available_plugins = [
            "Google Search",
            "Google Image Search",
            "YouTube",
            "Google Maps"
        ]
        self.plugin_functions = {
            "Google Search": "search(query, num_results, page)",
            "Google Image Search": "searchimages(query, num_results, page)",
            "YouTube": "searchvideos(query, num_results, page, sort_order, regionCode, relevanceLanguage)",
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
            "location": None, # city/country
            "timezone": None,
            "language": "en"
        }
        self.default_user_history = {
            "monthly_used_tokens": 0,
            "estimated_monthly_cost_eur": 0.0,
            "past_months_used_tokens": [],
            "past_months_cost_eur": []
        }
        self.default_channel_settings = {
            "location": None, # city/country
            "timezone": None,
            "language": "en",
            "systemprompt": self.gpt_prompt_precise,
            "creativity": 0.0,
            "autorespond": True,
            "num_of_last_messages_included": 5,
            "plugins": self.available_plugins, # TODO: by default no plugins active, only after adding api keys
            "debug_mode": False
        }
        self.num_results_default = 4
        self.default_user_secrets_folder = "user_secrets"
        self.default_user_history_folder = "user_history"
        self.default_user_settings_folder = "user_settings"
        self.log("KittyAI API initialized")
    
    def log(self,message,failure=False):
        if self.debug:
            if failure:
                print("\033[31m"+message+"\033[0m")
            else:
                print(message)
            print("--------")
    
    #############################
    ## Plugins
    #############################

    async def search(self,google_api_key,google_cx_id,query,num_results=4,page=1,):
        try:
            results = await api_google.search(google_api_key,google_cx_id,query,num_results,page)

            return str(results)
        
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
        
        

    async def searchimages(self,google_api_key,google_cx_id,query,num_results=4,page=1):
        try:
            results = await api_google.searchimages(google_api_key,google_cx_id,query,num_results,page)

            return str(results)
        
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

    async def searchvideos(self,google_api_key,query,num_results=4,page=1,sort_order="relevance",regionCode="US",relevanceLanguage="en"):
        try:
            results = await api_google.searchvideos(google_api_key,query,num_results,page,sort_order,regionCode,relevanceLanguage)
            
            return str(results)
        
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
    
    async def searchlocations(self,google_api_key,query,where=None,open_now=False,num_results=4,page=1):
        try:
            results = await api_google.searchlocations(
                google_api_key=google_api_key,
                query=query,
                where=where,
                open_now=open_now,
                num_results=num_results,
                page=page)
            
            return str(results)
        
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
            if not channel_settings["timezone"]:
                channel_settings["timezone"] = await helpertools.get_timezone(channel_settings["location"])
                # save the timezone to the channel settings
                await self.set_channel_settings(channel_id,"timezone",channel_settings["timezone"])

            prompt += await helpertools.get_date_and_time(channel_settings["location"],channel_settings["timezone"])+"\n"

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
            prompt += self.gpt_prompt_plugins_intro+"\n\n"
            prompt += "Plugins:\n"
            for plugin in channel_settings["plugins"]:
                # add plugin name and function
                prompt += plugin + " -> " + self.plugin_functions[plugin]+ "\n"
            
            # add num_results
            prompt += "\nnum_results default is " + str(self.num_results_default)+"\n\n"

            prompt += self.gpt_system_prompt_intro+" "

        # add system prompt
        # if no systemprompt in channel settings, use default
        if not "systemprompt" in channel_settings or not channel_settings["systemprompt"]:
            # if creativity is set to 0, use precise prompt
            if not "creativity" in channel_settings or channel_settings["creativity"] == 0.0:
                channel_settings["systemprompt"] = self.gpt_prompt_precise
            else:
                channel_settings["systemprompt"] = self.gpt_prompt_creative

        prompt += channel_settings["systemprompt"]

        return prompt


    async def process_commands(self,message,user_id,usable_plugins):
        # check if the user wants to use a plugin
        self.log("process_commands(message="+message+")")
        for plugin in usable_plugins:
            # add the function name to the list of plugin functions, without the parameters. e.g. "searchvideos"
            plugin_text_output = "..."
            found_plugin = False
            try:
                function_name = self.plugin_functions[plugin].split("(")[0]
                
                # check if any of the plugin functions is in the message and extract the function name including variables (e.g. "searchvideos("cats",4,1)")
                pattern = rf'{function_name}\((.*?)\)'
                match = re.search(pattern, message)
                if match:
                    found_plugin = True
                    params_str = match.group(1)
                    self.log("Found plugin function: "+function_name +" with parameters: "+params_str)

                    # Call the function with the extracted parameters and attach all api keys / secrets for the given plugin
                    plugin_secrets = []
                    for key in self.required_api_keys[plugin]:
                        plugin_secrets.append(await self.get_api_key(user_id,key))

                    path = "self." + function_name + "(" + ",".join(['"{}"'.format(secret) for secret in plugin_secrets]) + "," + params_str + ")"

                    self.log("Calling function: "+function_name+"("+params_str+") with secrets: "+str(self.required_api_keys[plugin]))
                    plugin_text_output = await eval(path)

                
            except Exception as e:
                self.log("Error: "+str(e),True)
                plugin_text_output = "Error: "+str(e)

            if found_plugin:
                # find function call again with regex and replace it with the output of the function
                pattern = rf'{function_name}\((.*?)\)'
                message = re.sub(pattern, plugin_text_output, message)
                self.log("Message after plugin function replacement: "+message)
        
        return message


    ####################
    ## API keys
    ####################

    async def get_api_key(self,user_id,key_type):
        # get the api key from the database
        self.log("get_api_key(user_id="+user_id+",key_type="+key_type+")")
        load_dotenv(self.default_user_secrets_folder+"/"+user_id+".env")
        key = os.getenv(key_type)
        if key == None:
            self.log("Error: API key not found: "+key_type,True)
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
        self.log("get_channel_settings(channel_id="+channel_id+",setting="+setting+")")
        # load channel settings json
        if os.path.exists('channel_settings.json'):
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
                    return self.default_channel_settings
        else:
            return None
    
    async def update_channel_setting(self,channel_id,setting,new_value):
        # update the channel settings to the database
        # settings: systemprompt, creativity, autorespond, num_of_last_messages_included, debug_mode
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
    
# async def run_bot():
#     ai = KittyAIapi(debug=True)
#     # prompt = await ai.get_system_prompt("481286403767140364","02sj")
#     # print(prompt)
#     await ai.process_commands(
#         "Here are some great restaurants:\n\nsearchlocations(\"Neapolitan style pizza\", \"Berlin Kreuzberg\", open_now=False, num_results=4, page=1)\n\nAny idea requests?",
#         "481286403767140364",
#         ["YouTube","Google Search","Google Maps", "Google Image Search"]
#         )

# asyncio.run(run_bot())
