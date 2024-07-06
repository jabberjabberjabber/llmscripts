import os
import re
import ftfy
import requests
import random
import time
import threading
import json
from datetime import datetime
import shutil
from spacy.lang.en import English
import base64
from tika import parser
from json_repair import repair_json
from natsort import os_sorted

class FileUtils:
    @staticmethod
    def get_basic_metadata(file_path):    
        created = os.path.getctime(file_path)
        modified = os.path.getmtime(file_path)
        return {
            'size': os.path.getsize(file_path),
            'created': datetime.fromtimestamp(created).isoformat(),
            'modified': datetime.fromtimestamp(modified).isoformat()
        }

    @staticmethod
    def move_and_rename(old_path, new_path):
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        shutil.move(old_path, new_path)

    @staticmethod
    def ensure_dir(directory):
        if not os.path.exists(directory):
            os.makedirs(directory)
    
    @staticmethod
    def clean_json(data):
        if data is None:
            return ""

        pattern = r'```json\s*(.*?)\s*```'
        match = re.search(pattern, data, re.DOTALL)

        if match:
            json_str = match.group(1).strip()
        else:
            json_str = re.search(r'\{.*\}', data, re.DOTALL)
            if json_str:
                json_str = json_str.group(0)
            else:
                return ftfy.fix_text(data)
        
        json_str = re.sub(r'\n', ' ', json_str)
        json_str = re.sub(r'["""]', '"', json_str)
        try:
            return json.loads(repair_json(json_str))
        except json.JSONDecodeError:
            return ftfy.fix_text(data)
        
    @staticmethod
    def read_file_content(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            return FileUtils.parse_with_tika(file_path)

    @staticmethod
    def parse_with_tika(file_path):
        parsed = parser.from_file(file_path)
        return parsed.get('content', '')

    @staticmethod
    def write_to_json(file_path, data):
        json_path = f"{file_path}_info.json"
        if os.path.exists(json_path):
            print(f"File already exists: {json_path}")
        with open(json_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        print(f"Result written to: {json_path}")
        
    @staticmethod
    def read_from_json(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                opened = file.read()
                return json.loads(opened)
        except:
            print(f"JSON error: {file_path}")
            return None

    @staticmethod
    def clean_content(content):
        if content is None:
            return ""
        content = ftfy.fix_text(content)
        content = re.sub(r'\n+', '\n', content)
        content = re.sub(r' +', ' ', content)
        return content.strip()

class FileCrawler:
    def __init__(self):
        self.file_categories = {
            "document": ["txt", "pdf", "doc", "docx", "md", "rtf"],
            "spreadsheet": ["xls", "xlsx", "csv", "ods"],
            "presentation": ["ppt", "pptx", "odp"],
            "image": ["jpg", "jpeg", "png", "gif", "bmp", "tiff"],
            "audio": ["mp3", "wav", "ogg", "flac"],
            "video": ["mp4", "avi", "mov", "wmv", "flv", "mkv"],
            "web": ["html", "htm", "xml", "css", "js"],
            "code": ["py", "java", "cpp", "c", "js", "php", "rb"],
            "archive": ["zip", "rar", "7z", "tar", "gz"]
        }

    def crawl(self, directory, recursive=False, categories=None):
        file_list = {}
        walker = os.walk(directory) if recursive else [next(os.walk(directory))]

        for root, _, files in walker:
            sorted_files = os_sorted(files)
            for file in sorted_files:
                file_path = os.path.join(root, file)
                file_extension = os.path.splitext(file)[1].lower().lstrip('.')
                if self.should_include_file(file_extension, categories):
                    category = self.get_file_category(file_extension)
                    if category not in file_list:
                        file_list[category] = []
                    file_list[category].append(self.get_file_info(file_path, file_extension))

        return file_list

    def get_files_with_json(self, directory):
        file_json_pairs = []
        for root, _, files in os.walk(directory):
            for file in files:
                if not file.endswith('_info.json'):
                    file_path = os.path.join(root, file)
                    json_path = f"{file_path}_info.json"
                    if os.path.exists(json_path):
                        file_json_pairs.append((file_path, json_path))
        return file_json_pairs

    def should_include_file(self, file_extension, categories):
        if not categories or 'all' in categories:
            return True
        return any(file_extension in self.file_categories.get(category, []) for category in categories)

    def get_file_category(self, file_extension):
        for category, extensions in self.file_categories.items():
            if file_extension in extensions:
                return category
        return "other"

    def get_file_info(self, file_path, file_extension):
        return {
            'path': file_path,
            'directory': os.path.dirname(file_path),
            'name': os.path.basename(file_path),
            'extension': file_extension,
            'category': self.get_file_category(file_extension),
            'metadata': FileUtils.get_basic_metadata(file_path)
        }

class TaskProcessor:
    def __init__(self, llm_processor, task_config_path):
        self.llm_processor = llm_processor
        self.task_config = FileUtils.read_from_json(task_config_path)
        
    def process_tasks(self, file_info, content, tasks):
        result = {'file_info': file_info}
        for task in tasks:
            try:
                if task not in self.task_config:
                    print(f"Invalid task: {task}")
                    result[task] = "Invalid task"
                    continue
                
                task_config = self.task_config.get(task)
                num_chunks = task_config.get('num_chunks')
                
                if task_config:
                    result[task] = self.llm_processor.process_text(
                        content=content,  
                        task=task_config,
                        num_chunks=num_chunks,
                    )
                result[task] = FileUtils.clean_json(result[task])    
            except Exception as e:
                print(f"Error processing task '{task}': {str(e)}")
                result[task] = f"Error: {str(e)}"
        return result

    def process_custom_task(self, content, instruction, parameters=None):
        task_config = {
            "instruction": instruction,
            "num_chunks": 1,
            "parameters": parameters or {
                "temperature": 0.7,
                "min_p": 0.05,
                "top_p": 0.9,
                "rep_pen": 1.05
            }
        }
        return self.llm_processor.process_text(content, task_config)

class LLMProcessor:
    def __init__(self, api_url, password="", model="chatML", prompt_config=None, chunk_size=512):
        self.api_url = api_url
        self.password = password
        self.genkey = f"KCP{''.join(str(random.randint(0, 9)) for _ in range(4))}"
        self.generated = False
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.password}'
        }   
        self.nlp = English()
        self.nlp.add_pipe('sentencizer')
        self.chunk_size = chunk_size
        self.prompt_config = prompt_config
        self.model = model
        self.chat_template = {}
        
    def interrogate_image(self, image_path):
        try:
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            payload = {
                'image': base64_image,
                'model': 'clip',  
            }
            response = requests.post(f"{self.api_url}/sdapi/v1/interrogate", json=payload, headers=self.headers)
            if response.status_code == 200:
                return response.json().get('caption', '')
            else:
                print(f"Image interrogation failed with status code {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"Error in image interrogation: {e}")
            return None

    def process_text(self, content, task, num_chunks=999):
        default_template = {
            "startTurn": "",
            "endSystemTurn": "",
            "endUserTurn": "\n\n",
            "endTurn": "\n\n",
            "systemRole": "Below is an instruction that describes a task. Write a response that appropriately completes the request.",
            "userRole": "### Instruction:",
            "assistantRole": "### Response:",
            "prependPrompt": "\n\n",
            "systemAfterPrepend": "",
            "postPrompt": "",
            "memorySystem": "",
            "memoryUser": "",
            "responseStart": "",
            "specialInstructions": ""
            }
        if self.prompt_config is not None:
            if os.path.exists(self.prompt_config):
                templates = FileUtils.read_from_json(self.prompt_config)
                self.chat_template = templates.get(model)
        else:
            self.chat_template = default_template
  
        if task is None:
            return
        
        cleaned_content = FileUtils.clean_content(content)
        self.tokens = self.get_token_count(json.dumps(cleaned_content))
        self.max_context_length = self.get_max_context()        
        if (self.tokens + 100) < self.max_context_length:
            if num_chunks == 0:
                print(f"Cannot fit content into context. Too many tokens: {self.tokens}")
                return 
            else:
                chunks = [cleaned_content]        
        else:
            chunks = self.chunkify(cleaned_content, num_chunks)
            
        results = []
        for chunk in chunks:
            prompt = self.get_template(instruction=task.get('instruction'), content=chunk)
            tokens = self.get_token_count(prompt)
            print(f"Tokens in prompt: {tokens}")
            
            if tokens > self.max_context_length:
                print(f"Warning: Content exceeds max context length. Tokens: {tokens}, Max: {self.max_context_length}")
                prompt = prompt[:self.max_context_length]  # This is a naive truncation and might break the prompt 
                tokens = self.get_token_count(prompt) 
                
            payload = {
                'prompt': prompt,
                'max_length': self.chunk_size,
                'max_context_length': self.max_context_length,
                **task.get('parameters', {})
            }
            
            result = self._call_api(payload)
            if result is not None:
                results.append(result)

        if not results:
            print("API call failed or returned no results")
            return None
        return " ".join(results)
        
    def chunkify(self, content, num_chunks=999):
        doc = self.nlp(content)
        sentences = list(doc.sents)
        chunks = []
        if not self.tokens:
            self.tokens = self.get_token_count(json.dumps(content))
            
        avg_tokens_per_sentence = max(1, int(self.tokens / len(sentences)))
       
        try:
            sentences_per_chunk = max(1, int(self.chunk_size / avg_tokens_per_sentence))
        except:
            print("Average tokens not valid -- check API connectivity")
            chunks = [0,'error']
            return chunks
        for i in range(0, len(sentences), sentences_per_chunk):
            chunk = sentences[i:i + sentences_per_chunk]
            chunks.append(" ".join(str(sent) for sent in chunk))
        
        if num_chunks > 0:
            if num_chunks >= len(chunks):
                return chunks
            elif num_chunks > 1:
                # Always include the first chunk
                selected_chunks = [chunks[0]]
                # Randomly select the rest from the remaining chunks
                selected_chunks.extend(random.sample(chunks[1:], num_chunks - 1))
                return selected_chunks
            elif num_chunks == 1:
                return [chunks[0]]  # If num_chunks is 1, return only the first chunk
            else:
                chunks = [0, 'error']
        return chunks
        	
    def get_template(self, instruction, content):
        template = self.chat_template
        system_part = (f"{template.get('bos', '')}"
                       f"{template.get('startTurn', '')}"
                       f"{template.get('startSystem', '')}"
                       f"{template.get('systemRole', '')}"
                       f"{template.get('systemAfterPrepend', '')}"
                       f"<text>{content}</text>"
                       f"{template.get('endSystemRole', '')}"
                       f"{template.get('memorySystem', '')}"
                       f"{template.get('endSystemTurn', '')}")

        # Construct user part
        user_part = (f"{template.get('startTurn', '')}"
                     f"{template.get('startUser', '')}"
                     f"{template.get('userRole', '')}"
                     f"{template.get('roleGap', '')}"
                     f"{template.get('memoryUser', '')}"
                     f"{instruction}"
                     
                     f"{template.get('endUserRole', '')}"
                     f"{template.get('endUserTurn', '')}")

        # Construct assistant part
        assistant_part = (f"{template.get('startTurn', '')}"
                          f"{template.get('startAssistant', '')}"
                          f"{template.get('assistantRole', '')}"
                          f"{template.get('roleGap', '')}"
                          f"{template.get('responseStart', '')}")

        # Combine all parts
        prompt = (f"{template.get('prependPrompt', '')}"
                  f"{system_part}"
                  f"{user_part}"
                  f"{assistant_part}"
                  f"{template.get('postPrompt', '')}"
                  f"{template.get('endTurn', '')}"
                  f"{template.get('eos', '')}")

        if template.get('specialInstructions') == '.rstrip()':
            prompt = prompt.rstrip()

        return prompt

    def _call_api(self, payload):
        payload['genkey'] = str(self.genkey)
        self.generated = False
        poll_thread = threading.Thread(target=self.poll_generation_status)
        poll_thread.start()
        try:
            response = requests.post(f"{self.api_url}/v1/generate/", json=payload, headers=self.headers)
            if response.status_code == 200:
                self.generated = True
                poll_thread.join()
                result = response.json()
                if 'results' in result and len(result['results']) > 0:
                    return result['results'][0].get('text')
        except Exception as e:
            print(f"Error communicating with API: {str(e)}")
        finally:
            self.generated = True
        return None

    def poll_generation_status(self):
        payload = {'genkey': self.genkey}
        while not self.generated:
            try:
                response = requests.post(f"{self.api_url}/extra/generate/check", json=payload, headers=self.headers)
                if response.status_code == 200:
                    result = response.json().get('results')[0].get('text')
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print(f"\r{result} ", end="\n", flush=True)
            except Exception as e:
                print(e)
                return
            time.sleep(2)
			
    def get_token_count(self, content):
        payload = {'prompt': content, 'genkey': self.genkey}
        try:
            response = requests.post(f"{self.api_url}/extra/tokencount", json=payload, headers=self.headers)
            if response.status_code == 200:
                return response.json().get('value', 0)
        except Exception as e:
            print(f"Error in get_token_count: {e}")
            return 0
			
    def get_max_context(self):
        try:
            response = requests.get(f"{self.api_url}/extra/true_max_context_length", headers=self.headers)
            if response.status_code == 200:
                return response.json().get('value', 0)
        except Exception as e:
            print(f"Error in get_max_context: {e}")
            return 0