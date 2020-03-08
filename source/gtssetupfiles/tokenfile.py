import json


def checktokenfile():
    try:
        with open("../token.json", "r"):
            return
    except FileNotFoundError:
        maketokenfile()


def maketokenfile():
    with open("../token.json", "w") as token_file:
        bot_token = input("Please input the bot account's token:\n")
        token_dict = {"botToken": bot_token}
        token_file.write(json.dumps(token_dict))
