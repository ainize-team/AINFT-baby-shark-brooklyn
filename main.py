import json
import os

import firebase_admin
import requests
from fastapi import FastAPI
from firebase_admin import credentials, db

# START LOAD ENV
print("Load Value From ENV")
twitter_api = os.environ.get("TWITTER_API")
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

# INIT FIREBASE
print("Initialize Firebase")
cred = credentials.Certificate(firebase_credentials)
firebase_admin.initialize_app(cred, firebase_configs)

# INIT FASTAPI
print("Run Fast API Server")
app = FastAPI()

# LOAD BROOKLYN DATA
print("Load Brooklyn data")
with open("./data.json", "r") as f:
    json.load(f)
    with open("./data.json", "r") as f:
        json_obj = json.load(f)

information = " ".join(json_obj["information"])
chat_logs = "\n".join([f"Human: {each['Human']}\nAI: {each['AI']}" for each in json_obj["logs"]])


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/chat")
def chat(text: str, twitter_id: str = ""):
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
    if twitter_id:
        ref = db.reference(twitter_id)
        data = ref.get()
        if data is None:
            return {
                "status_code": 200,
                "message": f"There is no data corresponding to the {twitter_id}."
            }
        if data["status"] != "completed":
            return {
                "status_code": 200,
                "message": f"We are collecting data corresponding to {twitter_id}."
            }
        twitter_chat_logs = ""
        for context_id, comments in data["data"].items():
            for idx, comment in enumerate(comments["comments"]):
                print(comment)
                req = comment["req"]
                res = comment["res"]
                if res[-1] == "?" or res[-1] == "!":
                    res = res
                elif res[-1] == ".":
                    res = res[:-1] + " doo doo doo doo doo doo."
                else:
                    res += " doo doo doo doo doo doo"
                twitter_chat_logs += f"Human: {req}\nAI: {res}"
                if idx != len(comments) - 1:
                    twitter_chat_logs += "\n"
        if twitter_chat_logs:
            prompt_text = f"{information}\n\n{twitter_chat_logs}\n{chat_logs}"
        else:
            prompt_text = f"{information}\n\n{chat_logs}"
    else:
        prompt_text = f"{information}\n\n{chat_logs}"
    request_text = f"{prompt_text}\nHuman: {text}\nAI: "
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
