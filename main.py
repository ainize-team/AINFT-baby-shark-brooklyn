import json
import os
import time
from typing import Dict, List

import firebase_admin
import requests
from fastapi import FastAPI
from firebase_admin import credentials, db

# START LOAD ENV
print("Load Value From ENV")
endpoint_url = os.environ.get("ENDPOINT_URL", "https://main-ainize-gpt-j-6b-589hero.endpoint.ainize.ai/generate")

firebase_credentials = {
    "type": os.environ.get("FIREBASE_TYPE"),
    "project_id": os.environ.get("FIREBASE_PROJECT_ID"),
    "private_key_id": os.environ.get("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.environ.get("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.environ.get("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.environ.get("FIREBASE_CLIENT_ID"),
    "auth_uri": os.environ.get("FIREBASE_AUTH_URI"),
    "token_uri": os.environ.get("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.environ.get("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.environ.get("FIREBASE_CLIENT_X509_CERT_URL")
}

firebase_configs = {
    "apiKey": os.environ.get("FIREBASE_API_KEY"),
    "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN"),
    "databaseURL": os.environ.get("FIREBASE_DATABASE_URL"),
    "projectId": os.environ.get("FIREBASE_PROJECT_ID"),
    "storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.environ.get("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.environ.get("FIREBASE_APP_ID"),
}

# END LOAD ENV
# Init Firebase
cred = credentials.Certificate(firebase_credentials)
firebase_admin.initialize_app(cred, firebase_configs)

# Init server and load data
app = FastAPI()
endpoint_url = 'https://main-ainize-gpt-j-6b-589hero.endpoint.ainize.ai/generate'


# Load Brooklyn data
json_obj = {}
print("Load Brooklyn data")
with open("./data_brooklyn.json", "r") as f:
    json_obj['brooklyn'] = json.load(f)

# Load William data
print("Load William data")
with open("./data_william.json", "r") as f:
    json_obj['william'] = json.load(f)

# Load Shark Family data
print("Load Shark Family data")
with open("./data_shark_family.json", "r") as f:
    json_obj['shark_family'] = json.load(f)


informations = {}
chat_logs = {}
for name, data in json_obj.items():
    informations[name] = " ".join(data["information"])
    chat_logs[name] = "\n".join([f"Human: {each['Human']}\nAI: {each['AI']}" for each in data["logs"]])


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/chat-brooklyn")
def chat(text: str):
    if "\n" in text:
        return {
            "status_code": 400,
            "message": "Newline characters cannot be entered."
        }
    if "AI:" in text or "Human:" in text or "<|endoftext|>" in text:
        return {
            "status_code": 400,
            "message": "You may have entered an invalid word."
        }
    if len(text) == 0 or len(text.strip()) == 0:
        return {
            "status_code": 400,
            "message": "There seems to be no content."
        }
    if len(text) >= 150:
        return {
            "status_code": 400,
            "message": "You cannot enter more than 150 characters."
        }

    prompt_text = f"{informations['brooklyn']}\n\n{chat_logs['brooklyn']}"
    if text[0].islower():
        text = text[0].upper() + text[1:]
    request_text = f"{prompt_text}\nHuman: {text}\nAI:"
    res = requests.post(endpoint_url, data={
        "text": request_text,
        "length": 50,
    })

    if res.status_code == 200:
        response_text = res.json()["0"]
        ret_text = ""
        for i in range(len(request_text), len(response_text)):
            if response_text[i] == "\n" or response_text[i:i + 7] == "Human: " or response_text[i:i + 4] == "AI: ":
                break
            ret_text += response_text[i]
        return {
            "status_code": res.status_code,
            "message": ret_text.strip()
        }
    else:
        return {
            "status_code": res.status_code,
            "message": "Some Error Occurs"
        }


@app.get("/chat-william")
def chat(text: str):
    if "\n" in text:
        return {
            "status_code": 400,
            "message": "Newline characters cannot be entered."
        }
    if "AI:" in text or "Human:" in text or "<|endoftext|>" in text:
        return {
            "status_code": 400,
            "message": "You may have entered an invalid word."
        }
    if len(text) == 0 or len(text.strip()) == 0:
        return {
            "status_code": 400,
            "message": "There seems to be no content."
        }
    if len(text) >= 150:
        return {
            "status_code": 400,
            "message": "You cannot enter more than 150 characters."
        }

    prompt_text = f"{informations['william']}\n\n{chat_logs['william']}"

    if text[0].islower():
        text = text[0].upper() + text[1:]
    request_text = f"{prompt_text}\nHuman: {text}\nAI:"
    res = requests.post(endpoint_url, data={
        "text": request_text,
        "length": 50,
    })

    if res.status_code == 200:
        response_text = res.json()["0"]
        ret_text = ""
        for i in range(len(request_text), len(response_text)):
            if response_text[i] == "\n" or response_text[i:i + 7] == "Human: " or response_text[i:i + 4] == "AI: ":
                break
            ret_text += response_text[i]
        return {
            "status_code": res.status_code,
            "message": ret_text.strip()
        }
    else:
        return {
            "status_code": res.status_code,
            "message": "Some Error Occurs"
        }


@app.get("/chat-shark-family")
def chat(text: str):
    if "\n" in text:
        return {
            "status_code": 400,
            "message": "Newline characters cannot be entered."
        }
    if "AI:" in text or "Human:" in text or "<|endoftext|>" in text:
        return {
            "status_code": 400,
            "message": "You may have entered an invalid word."
        }
    if len(text) == 0 or len(text.strip()) == 0:
        return {
            "status_code": 400,
            "message": "There seems to be no content."
        }
    if len(text) >= 150:
        return {
            "status_code": 400,
            "message": "You cannot enter more than 150 characters."
        }

    prompt_text = f"{informations['shark_family']}\n\n{chat_logs['shark_family']}"
    if text[0].islower():
        text = text[0].upper() + text[1:]
    request_text = f"{prompt_text}\nHuman: {text}\nAI:"
    res = requests.post(endpoint_url, data={
        "text": request_text,
        "length": 50,
    })

    if res.status_code == 200:
        response_text = res.json()["0"]
        ret_text = ""
        for i in range(len(request_text), len(response_text)):
            if response_text[i] == "\n" or response_text[i:i + 7] == "Human: " or response_text[i:i + 4] == "AI: ":
                break
            ret_text += response_text[i]
        return {
            "status_code": res.status_code,
            "message": ret_text.strip()
        }
    else:
        return {
            "status_code": res.status_code,
            "message": "Some Error Occurs"
        }