import requests


def login():
    password = "SuperSecret123!"
    return requests.post("https://example.com/login", data={"password": password})
