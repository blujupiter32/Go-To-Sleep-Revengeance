import json

bot_token = input("Please input the bot account's token:\n")
token_dict = {"botToken": bot_token}

with open("token.json", "w") as token_file:
    token_file.write(json.dumps(token_dict))
