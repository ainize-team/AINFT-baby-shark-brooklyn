import json
import os
import random
import asyncio
import requests

from typing import Any, Dict, AnyStr, List, Union

from ain.ain import Ain
from ain.types import ValueOnlyTransactionInput
from fastapi import FastAPI

endpoint_dict = {
    "gpt-j-endpoint": os.getenv("GPT-J-ENDPOINT", "https://main-ainize-gpt-j-6b-589hero.endpoint.ainize.ai/generate"),
    "ethical_filter": os.getenv("ETHICAL_FILTER",
                                "https://main-roberta-binary-sentiment-classification-ainize-team.endpoint.ainize.ai/classification")
}

# Connect AINetwork
provider_url = "https://testnet-api.ainetwork.ai"
brooklyn_private_key = os.environ["BROOKLYN_PRIVATE_KEY"]
william_private_key = os.environ["WILLIAM_PRIVATE_KEY"]
shark_family_private_key = os.environ["SHARK_FAMILY_PRIVATE_KEY"]

brooklyn_ain = Ain(provider_url)
william_ain = Ain(provider_url)
shark_family_ain = Ain(provider_url)

brooklyn_ain.wallet.addAndSetDefaultAccount(brooklyn_private_key)
william_ain.wallet.addAndSetDefaultAccount(william_private_key)
shark_family_ain.wallet.addAndSetDefaultAccount(shark_family_private_key)

loop = asyncio.get_event_loop()

# Init server and load data
app = FastAPI()

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

# Initial data
with open("./initial_data/prompt_information.json", "r") as f:
    prompt_information = json.load(f)

with open("./initial_data/bad_words.json", "r") as f:
    bad_words = json.load(f)


async def set_value(ref, ain, value):
    result = await ain.db.ref(ref).setValue(
        ValueOnlyTransactionInput(
            value=value,
            nonce=-1
        )
    )


def preprocessing_request(req: Dict[AnyStr, Any]):
    if "transaction" not in req or \
            "tx_body" not in req["transaction"] or \
            "operation" not in req["transaction"]["tx_body"]:
        return False, f'Invalid transaction : {req}', ""
    transaction = req["transaction"]["tx_body"]["operation"]
    transaction_type = transaction["type"]
    if transaction_type != "SET_VALUE":
        return False, f"Not supported transaction type : {transaction_type}", ""
    value = transaction["value"]
    return True, value["text"],


def check_input_text(text: str) -> int:
    if "\n" in text:
        return 1
    if "AI:" in text or "Human:" in text or "<|endoftext|>" in text:
        return 2
    if len(text) == 0 or len(text.strip()) == 0:
        return 3
    if len(text) >= 150:
        return 4
    return 0


def get_ethical_score(text) -> float:
    res = requests.get(endpoint_dict["ethical_filter"], params={"text": text})
    if res.status_code == 200:
        return res.json()["result"][1]
    else:
        return 0.0


def chat(text: str, prompt_text: str, ai_name: str, ain: Ain) -> str:
    grammatical_person = "singular" if ai_name in {"brooklyn", "william"} else "plural"
    if get_ethical_score(text) <= 0.4:
        random_idx = random.randint(0, len(bad_words["human"][grammatical_person]) - 1)
        message = bad_words["human"][grammatical_person][random_idx]
        return message
    if text[0].islower():
        text = text[0].upper() + text[1:]
    request_text = f"{prompt_text}\nHuman: {text}\nAI:"
    for step in range(3):
        res = requests.post(endpoint_dict["gpt-j-endpoint"], data={
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
            ret_text = ret_text.strip()
            if get_ethical_score(ret_text) > 0.6:
                return ret_text

    random_idx = random.randint(0, len(bad_words["bot"][grammatical_person]) - 1)
    return bad_words["bot"][grammatical_person][random_idx]


@app.post("/chat-brooklyn")
async def chat_brooklyn(req: Dict[AnyStr, Any] = None):
    is_valid, text, ref = preprocessing_request(req)
    if is_valid:
        error_code = check_input_text(text)
        if error_code:
            return ERROR_DICT[error_code]
        information = "\n".format(" ".join(prompt_information["brooklyn"]["information"]))
        logs = "\n".join(
            [f"Human: {each['Human']}\nAI: {each['AI']}" for each in prompt_information["brooklyn"]["logs"]])
        prompt = f"{information}\n\n{logs}"
        response_text = chat(text, prompt, "brooklyn", brooklyn_ain)
        result_ref = "/".join(ref.split('/')[:-1] + ["response"])
        loop.run_until_complete(set_value(result_ref, {"text": response_text}))


@app.post("/chat-william")
def chat_william(req: Dict[AnyStr, Any] = None):
    is_valid, text, ref = preprocessing_request(req)
    if is_valid:
        error_code = check_input_text(text)
        if error_code:
            return ERROR_DICT[error_code]
        information = "\n".format(" ".join(prompt_information["william"]["information"]))
        logs = "\n".join(
            [f"Human: {each['Human']}\nAI: {each['AI']}" for each in prompt_information["william"]["logs"]])
        prompt = f"{information}\n\n{logs}"
        response_text = chat(text, prompt, "william", william_ain)
        result_ref = "/".join(ref.split('/')[:-1] + ["response"])
        loop.run_until_complete(set_value(result_ref, {"text": response_text}))


@app.post("/chat-shark-family")
def chat_william(req: Dict[AnyStr, Any] = None):
    is_valid, text, ref = preprocessing_request(req)
    if is_valid:
        error_code = check_input_text(text)
        if error_code:
            return ERROR_DICT[error_code]
        information = "\n".format(" ".join(prompt_information["shark_family"]["information"]))
        logs = "\n".join(
            [f"Human: {each['Human']}\nAI: {each['AI']}" for each in prompt_information["shark_family"]["logs"]])
        prompt = f"{information}\n\n{logs}"
        response_text = chat(text, prompt, "shark_family", william_ain)
        result_ref = "/".join(ref.split('/')[:-1] + ["response"])
        loop.run_until_complete(set_value(result_ref, {"text": response_text}))
