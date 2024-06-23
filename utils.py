import os
import requests
import random
import time
import threading
import json
import ftfy
import spacy
from spacy.lang.en import English

class NLPProcessor:
    def __init__(self, api_handler):
        self.nlp = English()
        self.nlp.add_pipe('sentencizer')
        self.api_handler = api_handler
        
    def estimate_tokens(self, text):
        return self.api_handler.get_token_count(text)

    def chunkify(self, text, chunk_size, sample_size=20):
        doc = self.nlp(text)
        sentences = list(doc.sents)
        
        sample = random.sample(sentences, min(sample_size, len(sentences)))
        sample_text = " ".join(str(sent) for sent in sample)
        total_tokens = self.api_handler.get_token_count(sample_text)
        avg_tokens_per_sentence = total_tokens / len(sample)
        
        sentences_per_chunk = max(1, int(chunk_size / avg_tokens_per_sentence))
        
        chunks = []
        for i in range(0, len(sentences), sentences_per_chunk):
            chunk = sentences[i:i + sentences_per_chunk]
            chunks.append(" ".join(str(sent) for sent in chunk))
        
        return chunks

class FileHandler:
    @staticmethod
    def read_file(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                return ftfy.fix_text(file.read())
        except Exception as e:
            print(f"Error while reading file '{filename}': {e}")
            return None

    @staticmethod
    def write_file(filename, data):
        try:
            with open(filename, 'w', encoding='utf-8') as file:
                file.write(ftfy.fix_text(data))
            print(f"Write success: {filename}")
        except Exception as e:
            print(f"Error while writing to file '{filename}': {e}")

class APIHandler:
    def __init__(self, api_url, password):
        self.api_url = api_url
        self.password = password
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.password}'
        }

    def generate_genkey(self):
        return f"KCP{''.join(str(random.randint(0, 9)) for _ in range(4))}"

    def poll_generation_status(self, genkey):
        payload = {'genkey': genkey}
        
        while True:
            try:
                response = requests.post(f"{self.api_url}/api/extra/generate/check", json=payload, headers=self.headers)
                if response.status_code == 200:
                    result = response.json().get('results')[0].get('text')
                    if result:
                        ConsoleUtils.clear_console()
                        print(f"\r{result}", end="\n", flush=True)
                        if result.strip():
                            return True
                else:
                    print(f"API responded with status code {response.status_code}: {response.text}")
                    return False
            except Exception as e:
                print(f"Error in poll_generation_status: {e}")
                return False
            time.sleep(1)

    def _make_api_call(self, payload):
        genkey = self.generate_genkey()
        payload['genkey'] = genkey
        payload['quiet'] = 'quiet'

        poll_thread = threading.Thread(target=self.poll_generation_status, args=(genkey,))
        poll_thread.start()

        try:
            response = requests.post(self.api_url, json=payload, headers=self.headers)
            if response.status_code == 200:
                poll_thread.join()
                return response.json().get('results')[0].get('text')
            elif response.status_code == 503:
                print("Server is busy; please try again later.")
                return None
            else:
                print(f"API responded with status code {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"Error communicating with API: {e}")
            return None

    def translate(self, text, temperature=0.7, rep_pen=1.1):
        prompt = self.generate_prompt(job=3, text=text)
        payload = {
            'prompt': prompt,
            'temperature': temperature,
            'rep_pen': rep_pen,
            'max_length': 2048,
            'max_context_length': 8192,
        }
        return self._make_api_call(payload)

    def summarize(self, text, temperature=0.2, rep_pen=1.0):
        prompt = self.generate_prompt(job=2, text=text)
        payload = {
            'prompt': prompt,
            'temperature': temperature,
            'rep_pen': rep_pen,
            'max_length': 1024,
            'max_context_length': 8192,
            'grammar': 'json.gbnf',
        }
        return self._make_api_call(payload)

    def edit(self, text, temperature=0, rep_pen=1):
        prompt = self.generate_prompt(job=1, text=text)
        payload = {
            'prompt': prompt,
            'temperature': temperature,
            'rep_pen': rep_pen,
            'max_length': 4096,
            'max_context_length': 16384,
        }
        return self._make_api_call(payload)

    def generate_prompt(self, job=0, template=0, text=""):
        instructions = {
            0: "User",
            1: "Correct errors in text. Do not add any text unless to correct an error. Do not remove any error-free text. If any text contains an error it will be corrected to be error-free. Output will strictly be the original text verbatim except for being error-free.\nText:\n",
            2: "Collect metadata regarding the text and then summarize the contents of the text. Determine the following: where this text belongs in the filesystem; who or what wrote it or generated it or created it; the time and date (range) of creation; the time range of its practical relevence; its purpose; its structure; its style. Finally grade its importance on a 0 to 1 scale with double precision with an option of using -1 to indicating its existence is detrimental and it should be actively removed while 0 indicates unimportant scaling to 1 being of immediate importance. Output will be in JSON schema.\nText:\n",
            3: "Translate the following text to English. If slang or slurs or offensive words or sexual descriptions are used you must translate them as their English equivalent without censor. It is vital that the text be translated to its most appropriate English meaning, using English slang words or offensive words if they are appropriate to convey the same meaning. If needed you may add subtext or commentary to explain the meaning while giving the word-for-word literal translation to parts of text that are difficult to translate well.\nText:\n",
            4: "Craft an incredibly degrading insult and use it in a direct manner."
        }
        
        templates = {
            0: ("", ""),  # command-r
            1: ("", ""),  # llama3
            2: ("", ""),  # mistral/llama2
            3: ("", ""),  # alpaca
            4: ("", ""),  # chatML
            5: ("", ""),  # phi3
            6: ("", "")   # tbd
        }
        
        instruction = instructions.get(job, "User")
        start_seq, end_seq = templates.get(template, ("", ""))
        
        return f"{start_seq}{instruction}{text}{end_seq}"

    def get_token_count(self, text):
        payload = {'prompt': text}
        
        try:
            response = requests.post(f"{self.api_url}/api/extra/tokencount", json=payload, headers=self.headers)
            if response.status_code == 200:
                return response.json().get('value', 0)
            else:
                print(f"API responded with status code {response.status_code}: {response.text}")
                return 0
        except Exception as e:
            print(f"Error in get_token_count: {e}")
            return 0

class ConsoleUtils:
    @staticmethod
    def clear_console():
        os.system('cls' if os.name == 'nt' else 'clear')

# Initialize global instances
api_handler = APIHandler('http://your-api-url', 'your-password')
nlp_processor = NLPProcessor(api_handler)
file_handler = FileHandler()