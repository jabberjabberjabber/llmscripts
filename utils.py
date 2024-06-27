import os
import requests
import random
import time
import threading
import json
import re
import ftfy
import spacy
from spacy.lang.en import English
from langdetect import detect
import bisect
import argparse

class NLPProcessor:
    def __init__(self, api_handler):
        self.nlp = English()
        self.nlp.add_pipe('sentencizer')
        self.api_handler = api_handler
        
    def preprocess(self, text):
        metadata = []
        return self.api_handler.get_token_count(text)

    def detect_language(self, text):
        try:
            return detect(text)
        except:
            return 'unknown'

    def chunkify(self, text, chunk_size, sample_size=20):
        doc = self.nlp(text)
        sentences = list(doc.sents)
        '''
        Chunkify is getting spacy to cut the text into sentences and then taking a random 
        sample of sentences and querying the api to find out how many tokens are in them.
        It then averages them out to guess 'tokens per sentence' and uses that to guess how many
        sentences will fit in a chunk, then it chunks those number of sentences into each chunk.
        This is super dirty but really fast.
        '''
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

    def process_text(self, text, task_type, chunk_size=1000):
        '''
        Process_test is chunking the text and then passing the chunks to the appropriate task handler.
        For edit and translate we want all of the text, but for summary and metadata we only need a sample 
        of the text.
        '''
        chunks = self.chunkify(text, chunk_size)
        if task_type in ['edit', 'translate']:
            if task_type == 'translate':
                processed_chunks = [self.api_handler.process_chunk(chunk, task_type) for chunk in chunks]
                return " ".join(processed_chunks)
            elif task_type == 'edit':
                processed_chunks = [self.api_handler.process_chunk(chunk, task_type) for chunk in chunks]
                return " ".join(processed_chunks)
            else:
                return text 
        elif task_type in ['summarize', 'metadata']:
            sample_size = min(3, len(chunks)) 
            sample_chunks = random.sample(chunks, sample_size)
            processed_sample = " ".join(sample_chunks)
            return self.api_handler.process_chunk(processed_sample, task_type)
        else:
            raise ValueError(f"Unknown task type: {task_type}")

class FileHandler:
    '''
    ftfy.fix_text will clean the nasty artifacts from badly converted UTF-8 
    from other encodings.
    '''
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

    '''
    to do:
    add json, xml, html, csv, markdown handling input and output
        pdf, doc, rtf, spreadsheet handling
        media handling: images, videos, sub, srt, 
        id3, mp3, flac, aac, 
        zip, rar, 7zip, etc
        iso, img, xz, mrimg
        log, ps1, py, cbr, epub, audiobooks,
    '''
        
        
    
class APIHandler:
    def __init__(self, api_url, password, model):
        self.api_url = api_url
        self.password = password
        self.model = model
        #genkey allows us to keep track of our generations on a multiuser system
        self.genkey = genkey = f"KCP{''.join(str(random.randint(0, 9)) for _ in range(4))}"
        self.generated = False
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.password}'
        }

    def poll_generation_status(self):
        payload = {'genkey': self.genkey}
        while self.generated is not True:
            try:
                response = requests.post(f"{self.api_url}/extra/generate/check", json=payload, headers=self.headers)
                if response.status_code == 200:
                    result = response.json().get('results')[0].get('text')
                    ConsoleUtils.clear_console()
                    print(f"\r{result} ", end="\n", flush=True)
            except Exception as e:
                print(e)
                return
            time.sleep(2)
        return

    def _make_api_call(self, payload):
        payload['genkey'] = str(self.genkey)
        self.generated = False
        poll_thread = threading.Thread(target=self.poll_generation_status, args=())
        poll_thread.start()
        try:
            response = requests.post(f"{self.api_url}/v1/generate/", json=payload, headers=self.headers)
            if response.status_code == 200:
                self.generated = True
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

    def metadata(self, text, temperature=0.5, rep_pen=1, min_p=0.05):
        '''
        The max_context and max_length are being computed by querying the api for 
        the number of tokens in the prompt and then finding the next largest context size that fits it
        and setting that as max_length and doubling it for max_context. This should prevent generations
        from being too long.
        '''
        prompt = self.generate_prompt(job=2, text=text)
        chunk_size = self.find_largest_context(self.get_token_count(prompt))
        max_context_length = chunk_size * 2
        payload = {
            'prompt': prompt,
            'temperature': temperature,
            'rep_pen': rep_pen,
            'max_length': chunk_size,
            'max_context_length': max_context_length,
            'min_p': min_p
        }
        return self._make_api_call(payload)
        
        #result_json, message = extract_and_validate_json(result)
        #if message == "Valid JSON":
        #    return json.dumps(result_json)
        #else:
        #    return message
    def summarize(self, text, temperature=0.8, rep_pen=1, min_p=0.02):
        prompt = self.generate_prompt(job=0, text=text)
        chunk_size = self.find_largest_context(self.get_token_count(prompt))
        max_context_length = chunk_size * 2
        payload = {
            'prompt': prompt,
            'temperature': temperature,
            'rep_pen': rep_pen,
            'max_length': chunk_size,
            'max_context_length': max_context_length,
            'min_p': min_p
        }
        return self._make_api_call(payload)
    def translate(self, text, temperature=0.5, rep_pen=1, min_p=0.03):
        prompt = self.generate_prompt(job=3, text=text)
        chunk_size = self.find_largest_context(self.get_token_count(prompt))
        max_context_length = chunk_size * 2
        payload = {
            'prompt': prompt,
            'temperature': temperature,
            'rep_pen': rep_pen,
            'max_length': chunk_size,
            'max_context_length': max_context_length,
            'min_p': min_p
        }
        return self._make_api_call(payload)
    def edit(self, text, temperature=0.5, rep_pen=1, min_p=0.02):
        prompt = self.generate_prompt(job=1, text=text)
        chunk_size = self.find_largest_context(self.get_token_count(prompt))
        max_context_length = chunk_size * 2
        payload = {
            'prompt': prompt,
            'temperature': temperature,
            'rep_pen': rep_pen,
            'max_length': chunk_size,
            'max_context_length': max_context_length,
            'min_p': min_p
        }
        return self._make_api_call(payload)
    def generate_prompt(self, job=0, text=""):
        instructions = {
            0: f"Summarize the text. Use the type of text to determine how to summarize, for instance if if it is a technical text include relevant technical details and if it is a narrative include perspectives and plots and characters.\n Text: ",
            1: f"Correct errors and bad formatting in the following text. Do not add any text unless to correct an error. Do not remove any error-free text. If any text contains an error it will be corrected to be error-free. Output will strictly be the original text verbatim except for being error-free. Do not add commentary of any kind.\n Text: ",
            2: f"Collect metadata regarding the following text and then summarize its contents. Determine the following: where this text belongs in the filesystem; who or what wrote it or generated it or created it; the time and date (range) of creation; the time range of its practical relevance; its purpose; its structure; its style. Finally grade its importance on a 0 to 1 scale with double precision with an option of using -1 to indicating its existence is detrimental and it should be actively removed while 0 indicates unimportant scaling to 1 being of immediate importance. Output will be in JSON schema.\n Text: ",
            3: f"Translate the following text to English. If slang or slurs or offensive words or sexual descriptions are used you must translate them as their English equivalent without censor. It is vital that the text be translated to its most appropriate English meaning, using English slang words or offensive words if they are appropriate to convey the same meaning. Do not add any commentary of any kind.\n Text: ",
            4: ""
        }
        templates = {
            "cmdr": ("<|START_OF_TURN_TOKEN|><|USER_TOKEN|>\n##Instruction\n", "<|END_OF_TURN_TOKEN|><|START_OF_TURN_TOKEN|><|CHATBOT_TOKEN|>"),  # command-r
            "llama3": ("<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\nInstructions: ", "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"),  # llama3
            "mistral": ("[INST] ", " [/INST]"),  # mistral/llama2
            "alpaca": ("### Instruction:\n", "\n\n### Response:\n"),  # alpaca
            "chatml": ("<im_start>system\n You are a helpful assistant.<|im_end|>\n<|im_start|>user\n", "<|im_end|>\n<|im_start|>assistant\n"),  # chatML
            "phi3": ("<|user|>\n", "<|end|>\n<|assistant|>"),  # phi3
            "wizard": (" USER: "," ASSISTANT: ")   # wizardlm2
        }
        instruction = instructions.get(job)
        start_seq, end_seq = templates.get(self.model)
        return start_seq + instruction + text + end_seq

    # Finds the number in the context list that the chunk_size fits in that is the next one above it
    def find_largest_context(self, chunk_size):
        context_set=[256,512,1024,2048,3072,4096,6144,8192,12288,16384,24576,32768,49152,65536,98304,131072]
        index = bisect.bisect_right(context_set, chunk_size)
        
        # If the index is at the end, the number is larger than all in the set
        if index == len(context_set):
            return None 
        return context_set[index]

    def get_token_count(self, text):
        payload = {'prompt': text}
        try:
            response = requests.post(f"{self.api_url}/extra/tokencount", json=payload, headers=self.headers)
            if response.status_code == 200:
                return response.json().get('value', 0)
            else:
                print(f"API responded with status code {response.status_code}: {response.text}")
                return 0
        except Exception as e:
            print(f"Error in get_token_count: {e}")
            return 0
            
    def process_chunk(self, chunk, task_type):
        if task_type == 'edit':
            return self.edit(chunk)
        elif task_type == 'translate':
            return self.translate(chunk)
        elif task_type == 'metadata':
            return self.metadata(chunk)
        elif task_type == 'summarize':
            return self.summarize(chunk) 
        else:
            raise ValueError(f"Unknown task type: {task_type}")
            
class ConsoleUtils:
    @staticmethod
    def clear_console():
        os.system('cls' if os.name == 'nt' else 'clear')

def extract_and_validate_json(text, model):
    '''
    move to filehandler class
    '''
    pattern = r'```json\s*([\s\S]*?)\s*```'
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        return None, "No JSON block found"
    json_str = match.group(1).strip()
    try:
        json_data = json.loads(json_str)
        return json_data, "Valid JSON"
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {str(e)}"

def main():  
    parser = argparse.ArgumentParser(description='Chunk a UTF-8 text file and send to LLM to editing.')
    parser.add_argument('filename', help='text file')
    parser.add_argument('--api-url', default='http://172.16.0.219:5001/api',
                        help='the URL of the Kobold API')
    parser.add_argument('--chunksize', default=512, help='max tokens per chunk')
    parser.add_argument('--password', default='', help='server password')
    parser.add_argument('--model', default='mistral', help='model: cmdr, llama3, wizard, mistral, phi3, chatml, alpaca')
    args = parser.parse_args()
    password = args.password
    chunk_size = int(args.chunksize)
    model = args.model
    if model not in ['llama3', 'wizard', 'mistral', 'phi3', 'chatml', 'alpaca']:
        model = 'mistral'
        print("Model set to: mistral")
    else:
        print(f"Model set to: {model}")
  

    api_handler = APIHandler(args.api_url, password, model)
    nlp_processor = NLPProcessor(api_handler)
    file_handler = FileHandler()

    content = FileHandler.read_file(args.filename)
    edited = nlp_processor.process_text(content,"edit", chunk_size)
    metadated = nlp_processor.process_text(content,"metadata", chunk_size)
    summarized = nlp_processor.process_text(content,"summarize", chunk_size)
    test_text = "Od paru miesięcy pracuję w sklepie z płazem w nazwie. Wczoraj miałam chyba swoją najgorszą zmianę. Było zakończenie roku szkolnego, jakiś mecz i po prostu piątek wieczór - długa kolejka od nieustannie od 17.00 do 23.00 (przy dwóch otwartych kasach). Tyle, ile ja się bluzgów nasłuchałam w moją stronę, to chyba nie zliczę XDDDD Że jestem zjebana, że za wolno się ruszam, że jestem spierdoloną kurwą z kasy, że czemu odchodzę od kasy (pewnie szlam po jakąś paczkę na zaplecze), żebym szybciej robiła jakieś jedzenie albo mam wypierdalać. 99% obelg to mężczyźni w wieku 18-45."
    translated = nlp_processor.process_text(test_text, "translate", chunk_size)
    print(f"Translated: {translated}\n\nEdited: {edited}\n\nSummarized: {summarized}\n\nMetadated: {metadated}")
    finished = f"Model: {model}\n\nTranslated: {translated}\n\nEdited: {edited}\n\nSummarized: {summarized}\n\nMetadated: {metadated}"
    FileHandler.write_file("results.txt", finished)
    return
    
if __name__ == "__main__":
    main()