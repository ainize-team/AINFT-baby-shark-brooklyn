import json
import os
import random

import requests
from fastapi import FastAPI

# START LOAD ENV
print("Load Value From ENV")

# END LOAD ENV
# Init server and load data
app = FastAPI()
endpoint_url = "https://main-ainize-gpt-j-6b-589hero.endpoint.ainize.ai/generate"
bad_words_filter_endpoint_url = "https://main-roberta-binary-sentiment-classification-ainize-team.endpoint.ainize.ai/classification"

# Load Data
# TODO: move db
data = {}
for fn in os.listdir("./data"):
    file_name = os.path.splitext(fn)[0]
    print(f"Load {file_name} data")
    with open(f"./data/{fn}", "r", encoding="utf-8") as f:
        data[file_name] = json.load(f)

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
