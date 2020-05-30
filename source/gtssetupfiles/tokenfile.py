import json


def checktokenfile():
    try:
        bot_token_present = False  # Set up checklist of tokens we want to be in the token file before launching the bot
        google_token_present = False
        bot_token_value = ""  # Set up variables to capture the tokens we already have
        google_token_value = ""
        with open("./token.json", "r") as tokenfile:
            token_json = json.loads(tokenfile.read())
            if (
                token_json["botToken"] != ""
            ):  # If we already have the Discord bot token, record and capture it
                bot_token_present = True
                bot_token_value = token_json["botToken"]
            if (
                token_json["googleToken"] != ""
            ):  # If we already have the Google token, record and capture it
                google_token_present = True
                google_token_value = token_json["googleToken"]
            if (
                bot_token_present and google_token_present
            ):  # If we already have both, there's no point in making a new file
                return
            else:
                maketokenfile(
                    bot_token_present,
                    google_token_present,
                    bot_token_value,
                    google_token_value,
                )

    except FileNotFoundError:  # If the file is not there, we need to make one
        maketokenfile(
            bot_token_present, google_token_present, bot_token_value, google_token_value
        )

    except KeyError:  # If one of the tokens are not there, we need to add it in
        maketokenfile(
            bot_token_present, google_token_present, bot_token_value, google_token_value
        )


def maketokenfile(
    bot_token_present, google_token_present, bot_token_value, google_token_value
):
    with open("./token.json", "w") as token_file:
        token_dict = {}
        if (
            bot_token_present is False
        ):  # If the bot token is not present, capture it from the user input
            bot_token_value = input("Please input the bot account's token:\n")
        if (
            google_token_present is False
        ):  # If the google token is not present, capture it from the user input
            google_token_value = input(
                "Please input your Google Cloud Services API token:\n"
            )
        token_dict["botToken"] = bot_token_value  # Reconstruct the JSON
        token_dict["googleToken"] = google_token_value
        token_file.write(json.dumps(token_dict))  # Write the JSON into the file and end
