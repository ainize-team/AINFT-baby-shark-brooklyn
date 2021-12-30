import json
import os
import time
from typing import Dict, List

import firebase_admin
import requests
import tweepy
from TwitterAPI import TwitterAPI, TwitterPager
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

twitter_credential = {
    "CONSUMER_KEY": os.environ.get("TWITTER_CONSUMER_KEY"),
    "CONSUMER_SECRET": os.environ.get("TWITTER_CONSUMER_SECRET"),
    "ACCESS_TOKEN": os.environ.get("TWITTER_ACCESS_TOKEN"),
    "ACCESS_TOKEN_SECRET": os.environ.get("TWITTER_ACCESS_TOKEN_SECRET"),
}

# END LOAD ENV
# Init Firebase
cred = credentials.Certificate(firebase_credentials)
firebase_admin.initialize_app(cred, firebase_configs)

TWEET_FIELDS = 'conversation_id'


def connect_api():
    # To Search with user's Screen Name
    auth = tweepy.OAuthHandler(twitter_credential['CONSUMER_KEY'],
                               twitter_credential['CONSUMER_SECRET'])
    auth.set_access_token(twitter_credential['ACCESS_TOKEN'],
                          twitter_credential['ACCESS_TOKEN_SECRET'])
    api = tweepy.API(auth)

    # For request Replies with conversationID
    twapi = TwitterAPI(
        twitter_credential['CONSUMER_KEY'], twitter_credential['CONSUMER_SECRET'],
        twitter_credential['ACCESS_TOKEN'], twitter_credential['ACCESS_TOKEN_SECRET'],
        api_version='2'
    )
    return api, twapi


def get_user_id(api, screen_name: str):
    return api.get_user(screen_name=screen_name).id_str


def tweet_text_reply_tag_cleansing(txt: str) -> str:
    if txt[0] == "@":
        return " ".join(txt.split(" ")[1:])
    elif " @" in txt:
        return " ".join(txt.split(" @")[-1].split(" ")[1:])
    return txt


def get_new_tweets(api: tweepy.api, name: str, count: int = 5) -> Dict[str, Dict[str, str]]:
    print("Retrieving tweets")
    ret = {}
    tweets = api.user_timeline(screen_name=name, include_rts=False, count=count + 1, tweet_mode="extended")
    for tweet in tweets:
        ret[tweet.id_str] = {
            "tweet_id": tweet.id_str,
            "screen_name": tweet.user.screen_name,
            "text": tweet.full_text,
            "timestamp": tweet.created_at
        }
    return ret


def get_main_tweets(data: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    ret = {}
    for key in data:
        if key == data[key]['conversation_id']:
            ret[key] = data[key]
    return ret


def add_data(tweets: Dict[str, Dict[str, str]], twapi) -> Dict[str, Dict[str, str]]:
    print("Retrieving additional data")
    id_list = [tweets[key]["tweet_id"] for key in tweets]
    for _id in id_list:
        response = twapi.request(f'tweets/:{_id}', {'tweet.fields': TWEET_FIELDS})
        for item in response:
            tweets[_id][TWEET_FIELDS] = item[TWEET_FIELDS]
    return tweets


def init_data_for_db(main_tweets: Dict[str, Dict[str, str]]):
    ret = {}
    for main_tweet_id in main_tweets:
        main_tweet = main_tweets[main_tweet_id]
        screen_name = main_tweet["screen_name"]
        if screen_name not in ret:
            ret[screen_name] = {"data": {}, "status": "running", "updatedAt": time.time()}
        ret[screen_name]['data'][main_tweet_id] = {"comments": {}, "context": main_tweet['text']}
    return ret


def get_conversation_id(data_dict: Dict[str, Dict[str, str]]) -> List[str]:
    ret = set()
    for _id in data_dict:
        ret.add(data_dict[_id][TWEET_FIELDS])
    return list(ret)


def get_replies(twapi, conversation_list):
    replies = []
    for c_id in conversation_list:
        pager = TwitterPager(twapi, 'tweets/search/recent',
                             {
                                 'query': f'conversation_id:{c_id}',
                                 'tweet.fields': 'author_id,conversation_id,created_at,in_reply_to_user_id'
                             }
                             )
        for item in pager.get_iterator(wait=2):
            replies.append(item)
    return replies


def set_data(path, data):
    db.reference()
    ref = db.reference(path)
    ref.set(data)


def make_replies_to_conversation(replies: List[Dict[str, str]], db_data, screen_name, api) -> None:
    temp = {}
    twitter_user_id = get_user_id(api, screen_name)
    for reply in replies:
        conversation_id = reply['conversation_id']
        author_id = reply["author_id"]
        in_reply_to_user_id = reply['in_reply_to_user_id']
        text = tweet_text_reply_tag_cleansing(reply['text'])
        if conversation_id not in temp:
            temp[conversation_id] = []
        temp[conversation_id].append({"text": text, "from": author_id, "to": in_reply_to_user_id})

    for key in temp:
        if key not in db_data[screen_name]['data']:
            print(key)
            continue
        cnt, idx = 0, 0
        replies = temp[key][::-1]
        while idx < len(replies):
            value = replies[idx]
            if idx < len(replies) - 1 and value['to'] == twitter_user_id:
                conv = {"req": value['text'], 'res': replies[idx + 1]['text']}
                db_data[screen_name]['data'][key]['comments'][cnt] = conv
                idx += 2
                cnt += 1
            else:
                idx += 1


def crawl_twitter(screen_name: str) -> None:
    print("[twitter] Connect API")
    api, twapi = connect_api()
    print("[twitter] Get Tweets User:", screen_name)
    tweets = get_new_tweets(api, screen_name)
    main_tweets = get_main_tweets(add_data(tweets, twapi))
    db_data = init_data_for_db(main_tweets)
    print("[twitter] DataBaseInit")
    set_data(f"/{screen_name}", db_data[screen_name])
    conversation_ids = get_conversation_id(main_tweets)
    replies = get_replies(twapi, conversation_ids)
    make_replies_to_conversation(replies, db_data, screen_name, api)
    print("[twitter] Push Data")
    set_data(f"/{screen_name}/data", db_data[screen_name]['data'])
    set_data(f"/{screen_name}/status", "completed")
    set_data(f"/{screen_name}/updatedAt", time.time())


# Init server and load data
app = FastAPI()
endpoint_url = 'https://main-ainize-gpt-j-6b-589hero.endpoint.ainize.ai/generate'

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


@app.get("/makeTwitterData")
def make_twitter_data(screen_name: str):
    crawl_twitter(screen_name)
    return "OK"


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
