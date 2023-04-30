import plugins
import core.api_openai as api_openai
import json
import os
import asyncio
from dotenv import load_dotenv, dotenv_values



# this python class is used to process all the messages from the user, check if plugins are requested and calls them if needed

class KittyAIapi:
    def __init__(self,debug=False):
        self.debug = debug
        self.gpt_prompt_precise = "You are a helpful assistant called KittyAI. Provide concise and helpful responses."
        self.gpt_prompt_creative = "You are a helpful assistant called KittyAI."
        self.available_plugins = [
            "Google Search",
            "Google Image Search",
            "YouTube",
            "Google Maps"
        ]
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
        self.log("KittyAI API initialized")
    
    def log(self,message):
        if self.debug:
            print(message)
    
    async def get_system_prompt(self,channel_id):
        # load channel system prompt from json or else default
        # load channel plugins from json
        self.log("Loading system prompt")

    async def process_commands(self,message):
        # check if the user wants to use a plugin
        self.log("Processing commands")


    ####################
    ## API keys
    ####################

    async def get_api_key(self,user_id,key_type):
        # get the api key from the database
        self.log("Loading API key")
        load_dotenv("users/"+user_id+".env")
        key = os.getenv(key_type)
        if key == None:
            self.log("Error: API key not found")
        else:
            return key
    
    async def set_api_key(self, user_id, key_type, key):
        # set the api key to the database
        self.log("Saving API key")
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

    async def delete_api_key(self, user_id, key_type):
        # delete the api key from the database
        self.log("Deleting API key")
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

    ####################


    ####################
    ## User Settings
    ####################

    async def get_user_settings(self,user_id,setting="all"):
        # check if user_settings/user_id.json exists and load it
        self.log("Loading user settings")

        # load user settings json
        if os.path.exists('user_settings/'+user_id+'.json'):
            with open('user_settings/'+user_id+'.json') as f:
                user_settings = json.load(f)
                self.log("user_settings/"+user_id+".json:")
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
                            self.log("Error: Setting not found in default settings")


    ####################
    ## Channel Settings
    ####################
    
    async def get_channel_settings(self,channel_id,setting="all"):
        # get the channel settings from the database
        self.log("Loading channel settings")
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
                                self.log("Error: Setting not found in default settings")
                else:
                    # if no custom settings, return default settings
                    return self.default_channel_settings
        else:
            return None
    
    async def update_channel_setting(self,channel_id,setting,new_value):
        # update the channel settings to the database
        # settings: systemprompt, creativity, autorespond, num_of_last_messages_included, debug_mode
        self.log("Update channel settings")

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
        self.log("Resetting channel settings")
        
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
                    self.log("Channel settings not found")
        else:
            self.log("Channel settings file not found")

    ####################


    ####################
    ## Plugins
    ####################

    async def update_plugins(self,channel_id,plugin,new_status):
        # activate or deactivate a plugin for a channel
        self.log("Update plugin(s): " + plugin + " to " + new_status)

        if plugin == "all":

            if new_status == "activate":
                self.log("Activating all plugins")
                await self.update_channel_setting(channel_id,"plugins",self.available_plugins)

            elif new_status == "deactivate":
                self.log("Deactivating all plugins")
                await self.update_channel_setting(channel_id,"plugins",[])

            else:
                raise ValueError("Invalid value. Accepted values are 'activate' and 'deactivate'.")

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
                raise ValueError("Invalid value. Accepted values are 'activate' and 'deactivate'. Received: " + new_status)

    ####################
    
async def run_bot():
    ai = KittyAIapi(debug=False)
    settings = await ai.get_user_settings("481286403767140364","used_tokens")
    print(settings)

asyncio.run(run_bot())
