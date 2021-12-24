import json
import requests

from fastapi import FastAPI

'''
TODO
1. Modify to get necessary information from env
2. Define functions to be used by root ( ex, server check )
'''

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
