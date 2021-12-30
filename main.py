import os
import json
import time
import requests
from typing import Dict, List, Tuple

import tweepy
from TwitterAPI import TwitterAPI, TwitterRequestError, TwitterConnectionError, TwitterPager

import firebase_admin
from firebase_admin import credentials, db
from fastapi import FastAPI

# Init Firebase
cred = credentials.Certificate(firebase_credentials)
firebase_admin.initialize_app(cred, firebase_configs)

'''
TODO
1. Modify to get necessary information from env
2. Define functions to be used by root ( ex, server check )
'''

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
    tweets = api.user_timeline(screen_name=name, include_rts=False, count=count+1, tweet_mode="extended")
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

with open('./data.json', 'r') as f:
    json.load(f)
    with open('./data.json', 'r') as f:
        json_obj = json.load(f)

information = ' '.join(json_obj['information'])
chat_logs = '\n'.join([f'Human: {each["Human"]}\nAI: {each["AI"]}' for each in json_obj['logs']])
prompt_text = f'{information}\n\n{chat_logs}'


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/makeTwitterData")
def make_twitter_data(screen_name: str):
    crawl_twitter(screen_name)
    return "OK"


@app.get("/chat")
def chat(text: str):
    if '\n' in text:
        return {
            "status_code": 400,
            "message": "Newline characters cannot be entered."
        }
    if 'AI:' in text or 'Human:' in text or '<|endoftext|>' in text:
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
    request_text = f'{prompt_text}\nHuman: {text}\nAI: '
    res = requests.post(endpoint_url, data={
        'text': request_text,
        'length': 50,
    })
    if res.status_code == 200:
        response_text = res.json()['0']
        ret_text = ''
        for i in range(len(request_text), len(response_text)):
            if response_text[i] == '\n' or response_text[i:i + 7] == 'Human: ' or response_text[i:i + 4] == 'AI: ':
                break
            ret_text += response_text[i]
        return {
            'status_code': res.status_code,
            'message': ret_text
        }
    else:
        return {
            "status_code": res.status_code,
            "message": "Some Error Occurs"
        }

