import json
import os


def checksupportserver():

    if os.path.exists("./supportserver.json"):
        return
    else:
        supportserverinvite = input("Please input the invite link for your support server.\nIf you don't have one, just leave this blank.\n")
        supportserverdict = {"supportServerInvite": supportserverinvite}
        with open("./supportserver.json", "w") as supportserverjson:
            supportserverjson.write(json.dumps(supportserverdict))
