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
    def find_in_str(str):
        def _sub(X):
            ret = str.find(X)
            return ret if ret >= 0 else len(str)
        return _sub
    def retry_conditions(result):
        if len(result.strip()) == 0: return True
        if 'doo doo doo' not in result: return True
        return False
    retry = 3
    request_text = f'{prompt_text}\nHuman: {text}\nAI: '
    while retry:
        retry -= 1
        res = requests.post(endpoint_url, data={
            'text': request_text,
            'length': 50,
        })
        if res.status_code == 200:
            response_text = res.json()['0']
            ret_text = response_text[len(request_text):]
            ret_text = ret_text[:min(map( find_in_str(ret_text) , ["Human: ", "AI: ", '\n']))]
            if not retry_conditions(ret_text) or retry == 0:
                return {
                    'status_code': res.status_code,
                    'message': ret_text
                }
        elif retry == 0:
            return {
                "status_code": res.status_code,
                "message": "Some Error Occurs"
            }
