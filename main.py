import os
import argparse
import json
import re
import ftfy
import requests
import random
import time
import threading
from collections import defaultdict
from tika import parser
from spacy.lang.en import English
from fast_langdetect import detect_langs
import bisect

def is_not_english(text):
    text = ftfy.fix_text(text)
    text = re.sub(r'\n', '', text)
    lang = detect_langs(text)
    if lang == 'en':
        return False
    else:
        return True
        
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

class ConsoleUtils:
    @staticmethod
    def clear_console():
        os.system('cls' if os.name == 'nt' else 'clear')
        
def parse_document(file_path):
    parsed = parser.from_file(file_path)
    return parsed['content'], parsed['metadata']
    
class DocumentProcessor:
    def __init__(self, api_url, password, model, chunk_size):
        self.api_url = api_url
        self.password = password
        self.model = model
        self.chunk_size = chunk_size
        self.nlp = English()
        self.nlp.add_pipe('sentencizer')
        self.genkey = f"KCP{''.join(str(random.randint(0, 9)) for _ in range(4))}"
        self.generated = False
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.password}'
    }
    def get_file_type(self, filename):
        ext = os.path.splitext(filename)[1].lower()
        document_types = {
            '.txt': 'Text', '.pdf': 'PDF', '.doc': 'Word', '.docx': 'Word',
            '.xls': 'Excel', '.xlsx': 'Excel', '.ppt': 'PowerPoint', 
            '.pptx': 'PowerPoint', '.csv': 'CSV',
            '.xml': 'XML', '.html': 'HTML', '.htm': 'HTML'
        }
        if ext not in document_types:
            return None
        else:
            return document_types.get(ext)
    def chunkify(self, cleaned_text, sample_size=20):
        
        doc = self.nlp(cleaned_text)
        
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
        
        total_tokens = self.get_token_count(sample_text)
        
        avg_tokens_per_sentence = total_tokens / len(sample)
        
        sentences_per_chunk = max(1, int(self.chunk_size / avg_tokens_per_sentence))
        
        chunks = []
        for i in range(0, len(sentences), sentences_per_chunk):
            chunk = sentences[i:i + sentences_per_chunk]
            chunks.append(" ".join(str(sent) for sent in chunk))
        return chunks

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
        result = self._make_api_call(payload)
        if self.model == 'wizard':
            result_json, message = self.extract_and_validate_json(result)
            if message == "Valid JSON":
                return result_json
            else:
                return message
        else:
            return result
            
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
        json_schema = "{\"file name\": <file name>, \"file_path\": <file path>, \"creator\": <creator>, \"creation_date\": <date>, \"relevance_period\": \"<date> to <date>\", \"purpose\": <purpose>, \"structure\": <structure>, \"style\": <style>, \"importance\": <a float between 0 and 1>}"
        instructions = {
            0: f"Summarize the text. Use the type of text to determine how to summarize, for instance if if it is a technical text include relevant technical details and if it is a narrative include perspectives and plots and characters.\n Text: ",
            1: f"Correct errors and bad formatting in the following text. Do not add any text unless to correct an error. Do not remove any error-free text. If any text contains an error it will be corrected to be error-free. Output will strictly be the original text verbatim except for being error-free. Do not add commentary of any kind.\n Text: ",
            2: f"Collect metadata regarding the following text. Determine the following: where this text belongs in the filesystem; who or what wrote it or generated it or created it; the time and date (range) of creation; the time range of its practical relevance; its purpose; its structure; its style. Output will be in JSON schema as follows: {json_schema}\n Text: ",
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
                return 
                
        except Exception as e:
            print(f"Error in get_token_count: {e}")
            return       
            
            
    def process_chunk(self, chunk, task):
        if task == 'translate':
            return self.translate(chunk)
        if task == 'edit':
            return self.edit(chunk)
        if task == 'summarize':
            return self.summarize(chunk) 
        if task == 'metadata':
            return self.metadata(chunk)
        else:
            raise ValueError(f"Unknown task")
            
            
    def extract_and_validate_json(self, text):
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
    def process_text(self, file_info, tasks, chunk_size=1000):
        '''
        Process_test is chunking the text and then passing the chunks to the appropriate task handler.
        For edit and translate we want all of the text, but for summary and metadata we only need a sample 
        of the text.
        '''
        content, tika_metadata = parse_document(os.path.join(file_info['location'], file_info['name']))
        
        cleaned_content = self.clean_text(content)
       
        result = {'file_info': file_info, 'tika_metadata': tika_metadata }
        
        chunks = self.chunkify(cleaned_content, chunk_size)
        
        if is_not_english(cleaned_content) and 'translate' in tasks:
            translated_chunks = [self.process_chunk(chunk, 'translate') for chunk in chunks]
            chunks = translated_chunks
            result['translate'] = " ".join(translated_chunks)
    
        for task in tasks:
            if 'edit' in task:
                processed_chunks = [self.process_chunk(chunk, 'edit') for chunk in chunks]
                result['edit'] = " ".join(processed_chunks)
            elif 'summarize' in task:
                sample_size = min(4, len(chunks)) 
                sample_chunks = random.sample(chunks, sample_size)
                processed_sample = " ".join(sample_chunks)
                result['summarize'] = self.process_chunk(processed_sample, 'summarize')
            elif 'metadata' in task:
                sample_size = min(2, len(chunks)) 
                sample_chunks = random.sample(chunks, sample_size)
                processed_sample = " ".join(sample_chunks)
                result['metadata'] = self.process_chunk(processed_sample, 'metadata')
            
        return result
    def clean_text(self, text):
        if text is None:
            return ""
        text = ftfy.fix_text(text)
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()
class FileCrawler:
    def __init__(self, document_processor):
        self.document_processor = document_processor

    def find_and_process_files(self, directory, recursive=False, file_types=None, tasks=None):
        file_list = defaultdict(list)
        file_handler = FileHandler()
        
        walker = os.walk(directory) if recursive else [next(os.walk(directory))]
        for root, _, files in walker:
            for file in files:
                file_path = os.path.join(root, file)
                file_name, file_ext = os.path.splitext(file)
                file_type = self.document_processor.get_file_type(file)
                if (file_types is None or file_type in file_types) and file_type is not None:
                    file_info = {
                        'location': root,
                        'name': file,
                        'basename': file_name,
                        'ext': file_ext,
                        'type': file_type
                    }
                    if tasks is not None:
                        processed_info = self.document_processor.process_text(file_info, tasks)
                        json_filename = f"{file_name}_info.json"
                        file_handler.write_file(os.path.join(root, json_filename), json.dumps(processed_info, indent=2))
                        file_info['info_file'] = json_filename
                    file_list[file_type].append(file_info)
        return file_list
def main():
    parser = argparse.ArgumentParser(description='Process documents in filesystem')
    parser.add_argument('--api-url', default='http://172.16.0.219:5001/api',
                        help='the URL of the Kobold API')
    parser.add_argument('--chunksize', default=512, help='max tokens per chunk')
    parser.add_argument('--password', default='', help='server password')
    parser.add_argument('--model', default='wizard', help='model: cmdr, llama3, wizard, mistral, phi3, chatml, alpaca')
    parser.add_argument('directory', help='Directory to search')
    parser.add_argument('--recursive', action='store_true', help='Search recursively')
    parser.add_argument('--types', nargs='+', help='File types to search for (e.g., PDF Word)')
    parser.add_argument('--tasks', nargs='+',  default='info', help='Tasks: metadata, summarize, translate, edit, info, all')
    args = parser.parse_args()
    password = args.password
    chunk_size = int(args.chunksize)
    model = args.model
    if model not in ['llama3', 'wizard', 'mistral', 'phi3', 'chatml', 'alpaca', 'cmdr']:
        model = 'wizard'
        print("Model set to: wizard")
    else:
        print(f"Model set to: {model}")
    if 'all' in args.tasks:
        tasks = {'info','metadata','summarize','translate','edit'}
    else:
        tasks = args.tasks 
    #test_text = "Od paru miesięcy pracuję w sklepie z płazem w nazwie. Wczoraj miałam chyba swoją najgorszą zmianę. Było zakończenie roku szkolnego, jakiś mecz i po prostu piątek wieczór - długa kolejka od nieustannie od 17.00 do 23.00 (przy dwóch otwartych kasach). Tyle, ile ja się bluzgów nasłuchałam w moją stronę, to chyba nie zliczę XDDDD Że jestem zjebana, że za wolno się ruszam, że jestem spierdoloną kurwą z kasy, że czemu odchodzę od kasy (pewnie szlam po jakąś paczkę na zaplecze), żebym szybciej robiła jakieś jedzenie albo mam wypierdalać. 99% obelg to mężczyźni w wieku 18-45."

    document_processor = DocumentProcessor(args.api_url, args.password, args.model, int(args.chunksize))

    file_crawler = FileCrawler(document_processor)

    file_list = file_crawler.find_and_process_files(args.directory, args.recursive, args.types, tasks)
    
    #translated = document_processor.process_text(test_text, "translate", chunk_size)
    for file_type, files in file_list.items():       
        print(f"\n{file_type} files:")
        for file in files:
            print(f"  {file['name']} - {file['location']}")
            if 'info_file' in file:
                print(f"    Info: {file['info_file']}")
    total_files = sum(len(files) for files in file_list.values())
    print(f"\nTotal files found: {total_files}")
if __name__ == "__main__":
    main()
