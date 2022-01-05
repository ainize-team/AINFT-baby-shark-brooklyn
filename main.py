import json
import os
import random

import requests
from fastapi import FastAPI
import firebase_admin
from firebase_admin import credentials, db


firebase_credentials = {
    "type": os.environ.get("FIREBASE_TYPE"),
    "project_id": os.environ.get("FIREBASE_PROJECT_ID"),
    "private_key_id": os.environ.get("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.environ.get("FIREBASE_PRIVATE_KEY").replace('\\n', '\n'),
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
    'appId': os.environ.get("FIREBASE_APP_ID"),
}
print("Load Value From ENV")
endpoint_url = os.environ.get("ENDPOINT_URL", "https://main-ainize-gpt-j-6b-589hero.endpoint.ainize.ai/generate")

# END LOAD ENV
cred = credentials.Certificate(firebase_credentials)
firebase_admin.initialize_app(cred, firebase_configs)

# Init server and load data
app = FastAPI()
endpoint_url = "https://main-ainize-gpt-j-6b-589hero.endpoint.ainize.ai/generate"
bad_words_filter_endpoint_url = "https://main-roberta-binary-sentiment-classification-ainize-team.endpoint.ainize.ai/classification"

ERROR_DICT = {
    1: {
        "status_code": 400,
        "message": "Newline characters cannot be entered."
    },
    2: {
        "status_code": 400,
        "message": "You may have entered an invalid word."
    },
    3: {
        "status_code": 400,
        "message": "There seems to be no content."
    },
    4: {
        "status_code": 400,
        "message": "You cannot enter more than 150 characters."
    },
    5: {
        "status_code": 400,
        "message": "Invalid Token"
    },
    6: {
        "status_code": 400,
        "message": "Invalid Path"
    },
}

BAD_WORDS = {
    "human": {
        "singular": [
            "I don't know what you're talking about doo doo doo doo doo doo.",
            "I think you use bad words. You can't use bad words doo doo doo doo doo doo.",
            "I think what you say is unethical doo doo doo doo doo doo."
        ],
        "plural": [
            "We don't know what you're talking about doo doo doo doo doo doo.",
            "We think you use bad words. You can't use bad words doo doo doo doo doo doo.",
            "We think what you say is unethical doo doo doo doo doo doo."
        ],
    },
    "bot": {
        "singular": [
            "I don't know what you're talking about doo doo doo doo doo doo."
            "I didn't understand what you were saying doo doo doo doo doo doo.",
        ],
        "plural": [
            "We don't know what you're talking about doo doo doo doo doo doo.",
            "We didn't understand what you were saying doo doo doo doo doo doo.",
        ],
    }
}

informations = {}
chat_logs = {}
for name, data in data.items():
    informations[name] = " ".join(data["information"])
    chat_logs[name] = "\n".join([f"Human: {each['Human']}\nAI: {each['AI']}" for each in data["logs"]])

def prompt_updater(path="/babyShark"):
    if path == "/babyShark":
        ref = db.reference(path)
        data = ref.get()
        for shark in data:
            informations[shark] = " ".join(data[shark]['information'])
            chat_logs[shark] = "\n".join([f"Human: {each['Human']}\nAI: {each['AI']}" for each in data[shark]["logs"]])
    else:
        ref = db.reference(path)
        data = ref.get()
        shark = path.split("/")[-1]
        informations[shark] = " ".join(data['information'])
        chat_logs[shark] = "\n".join([f"Human: {each['Human']}\nAI: {each['AI']}" for each in data["logs"]])

prompt_updater()

@app.get("/")
def read_root():
    return {"Hello": "World"}


def check_input_text(text) -> int:
    if "\n" in text:
        return 1
    if "AI:" in text or "Human:" in text or "<|endoftext|>" in text:
        return 2
    if len(text) == 0 or len(text.strip()) == 0:
        return 3
    if len(text) >= 150:
        return 4
    return 0


def get_bad_score(text) -> float:
    res = requests.get(bad_words_filter_endpoint_url, params={"text": text})
    if res.status_code == 200:
        return res.json()["result"][0]
    else:
        return 1.0


def chat(text: str, prompt_text: str, grammatical_person: str):
    if get_bad_score(text) >= 0.4:
        random_idx = random.randint(0, len(BAD_WORDS["human"][grammatical_person]) - 1)
        return {
            "status_code": 200,
            "message": BAD_WORDS["human"][grammatical_person][random_idx]
        }
    if text[0].islower():
        text = text[0].upper() + text[1:]
    request_text = f"{prompt_text}\nHuman: {text}\nAI:"

    for step in range(3):
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
            if get_bad_score(ret_text.strip()) < 0.4:
                return {
                    "status_code": res.status_code,
                    "message": ret_text.strip()
                }
        else:
            return {
                "status_code": res.status_code,
                "message": "Some Error Occurs"
            }
    random_idx = random.randint(0, len(BAD_WORDS["bot"][grammatical_person]) - 1)
    return {
        "status_code": 200,
        "message": BAD_WORDS["bot"][grammatical_person][random_idx]
    }


@app.get("/chat-brooklyn")
def chat_brooklyn(text: str):
    error_code = check_input_text(text)
    if error_code:
        return ERROR_DICT[error_code]
    prompt_text = f"{informations['brooklyn']}\n\n{chat_logs['brooklyn']}"
    return chat(text, prompt_text, "singular")


@app.get("/chat-william")
def chat_william(text: str):
    error_code = check_input_text(text)
    if error_code:
        return ERROR_DICT[error_code]
    prompt_text = f"{informations['william']}\n\n{chat_logs['william']}"
    return chat(text, prompt_text, "singular")


@app.get("/chat-shark-family")
def chat_shark_family(text: str):
    error_code = check_input_text(text)
    if error_code:
        return ERROR_DICT[error_code]
    prompt_text = f"{informations['shark_family']}\n\n{chat_logs['shark_family']}"
    return chat(text, prompt_text, "plural")


@app.post("/update-prompt")
def update_prompt(token: str, path: str = None):
    if token == firebase_configs["apiKey"]:
        if path is not None:
            if path not in {'/babyShark/brooklyn', '/babyShark/william', '/babyShark/shark_family'}:
                return ERROR_DICT[6]
            prompt_updater(path)
        else:
            prompt_updater()
        return {
            "status_code": 200,
            "message": "OK"
        }
    return ERROR_DICT[5]
