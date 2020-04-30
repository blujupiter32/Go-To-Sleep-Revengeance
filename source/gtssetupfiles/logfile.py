import os


def checklogdirectory():
    if not os.path.exists("./logs"):
        os.mkdir("./logs")