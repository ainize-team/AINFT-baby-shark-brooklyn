import os
import random

import firebase_admin
import requests
from fastapi import FastAPI
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

informations = {}
chat_logs = {}
bad_words = {}


def bad_words_updater():
    global bad_words
    ref = db.reference("/BAD_WORDS")
    bad_words = ref.get()


def prompt_updater(path="/babyShark"):
    global informations, chat_logs
    if path == "/babyShark":
        ref = db.reference(path)
        data = ref.get()
        for ai_name in data:
            informations[ai_name] = " ".join(data[ai_name]['information'])
            chat_logs[ai_name] = "\n".join(
                [f"Human: {each['Human']}\nAI: {each['AI']}" for each in data[ai_name]["logs"]])
    else:
        ref = db.reference(path)
        data = ref.get()
        ai_name = path.split("/")[-1]
        informations[ai_name] = " ".join(data['information'])
        chat_logs[ai_name] = "\n".join([f"Human: {each['Human']}\nAI: {each['AI']}" for each in data["logs"]])


prompt_updater()
bad_words_updater()

# Init server and load data
app = FastAPI()
endpoint_url = "https://main-ainize-gpt-j-6b-589hero.endpoint.ainize.ai/generate"
bad_words_filter_endpoint_url = \
    "https://main-roberta-binary-sentiment-classification-ainize-team.endpoint.ainize.ai/classification"

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


def chat_log_writer(user_text: str, response: str, ai_name: str):
    ref = db.reference("/chat_logs")
    ref.push({"user_text": user_text, "ai_name": ai_name, "response": response})


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


@app.get("/")
def read_root():
    return {"Hello": "World"}


def get_bad_score(text) -> float:
    res = requests.get(bad_words_filter_endpoint_url, params={"text": text})
    if res.status_code == 200:
        return res.json()["result"][0]
    else:
        return 1.0


def chat(text: str, prompt_text: str, ai_name: str):
    grammatical_person = "singular" if ai_name in {"brooklyn", "william"} else "plural"
    if get_bad_score(text) >= 0.4:
        random_idx = random.randint(0, len(bad_words["human"][grammatical_person]) - 1)
        response = {
            "status_code": 200,
            "message": bad_words["human"][grammatical_person][random_idx]
        }
        chat_log_writer(text, response, ai_name)
        return response
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
                response = {
                    "status_code": res.status_code,
                    "message": ret_text.strip()
                }
                chat_log_writer(text, response, ai_name)
                return response
        else:
            response = {
                "status_code": res.status_code,
                "message": "Unexpected Error Occurs"
            }
            chat_log_writer(text, response, ai_name)
            return response
    random_idx = random.randint(0, len(bad_words["bot"][grammatical_person]) - 1)
    response = {
        "status_code": 200,
        "message": bad_words["bot"][grammatical_person][random_idx]
    }
    chat_log_writer(text, response, ai_name)
    return response


@app.get("/chat-brooklyn")
def chat_brooklyn(text: str):
    error_code = check_input_text(text)
    if error_code:
        return ERROR_DICT[error_code]
    prompt_text = f"{informations['brooklyn']}\n\n{chat_logs['brooklyn']}"
    return chat(text, prompt_text, "brooklyn")


@app.get("/chat-william")
def chat_william(text: str):
    error_code = check_input_text(text)
    if error_code:
        return ERROR_DICT[error_code]
    prompt_text = f"{informations['william']}\n\n{chat_logs['william']}"
    return chat(text, prompt_text, "william")


@app.get("/chat-shark-family")
def chat_shark_family(text: str):
    error_code = check_input_text(text)
    if error_code:
        return ERROR_DICT[error_code]
    prompt_text = f"{informations['shark_family']}\n\n{chat_logs['shark_family']}"
    return chat(text, prompt_text, "shark_family")


@app.post("/update")
def update_prompt(token: str, path: str = None):
    if token == firebase_configs["apiKey"]:
        if path is not None:
            if path not in {"/babyShark/brooklyn",
                            "/babyShark/william",
                            "/babyShark/shark_family",
                            "/bad_words"
                            }:
                return ERROR_DICT[6]
            if path == "/bad_words":
                bad_words_updater()
            else:
                prompt_updater(path)
        else:
            prompt_updater()
        return {
            "status_code": 200,
            "message": "OK"
        }
    return ERROR_DICT[5]
