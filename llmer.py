import os
import re
import ftfy
import requests
import random
import time
import threading
import bisect
from spacy.lang.en import English
import base64


class LLMProcessor:
    def __init__(self, api_url, password="", model="wizard", chunk_size=512):
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


    def interrogate_image(self, image_path):
        try:
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            payload = {
                'image': base64_image,
                'model': 'clip',  # KoboldCpp uses CLIP for image interrogation
                'max_length': 2048,
                'max_context_length': 8192
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

    def process_text(self, content, task, num_chunks=None):
        cleaned_content = self.cleanup_content(content)
        max_context_length = self.get_from_api("true_max_context_length")
        temp = []
        chunks = self.chunkify(cleaned_content, num_chunks=num_chunks)
        if num_chunks is not None:
            temp.append(" ".join(chunks))
            chunks = temp
        for chunk in chunks:    
            prompt = self.prompt_template(task.get('instruction'), content=chunk)
            tokens = self.get_token_count(prompt)
            if tokens > max_context_length:
                print(f"Too many tokens: {tokens} in for chunk")
                return     
                   
            payload = {
                'prompt': prompt,
                'max_length': tokens,
                'max_context_length': max_context_length,
                **task.get('parameters', {})
            }
            return self._call_api(payload)
            
    def chunkify(self, content, sample_size=20, num_chunks=None):
        doc = self.nlp(content)
        sentences = list(doc.sents)
        
        sample = sentences if len(sentences) <= sample_size else random.sample(sentences, sample_size)
        
        sample_text = " ".join(str(sent) for sent in sample)
        total_tokens = self.get_token_count(sample_text)
        avg_tokens_per_sentence = total_tokens / len(sample)
        
        try:
            sentences_per_chunk = max(1, int(self.chunk_size / avg_tokens_per_sentence))
        except:
            print("Average tokens not valid -- check API connectivity")
            return []

        chunks = [" ".join(str(sent) for sent in sentences[i:i + sentences_per_chunk]) 
                  for i in range(0, len(sentences), sentences_per_chunk)]
        
        if num_chunks:
            if num_chunks > len(chunks):
                return chunks
            elif num_chunks > 1:
                # Always include the first chunk
                selected_chunks = [chunks[0]]
                # Randomly select the rest from the remaining chunks
                selected_chunks.extend(random.sample(chunks[1:], num_chunks - 1))
                return selected_chunks
            else:
                return [chunks[0]]  # If num_chunks is 1, return only the first chunk
        else:
            return chunks
    def prompt_template(self, instruction, content ):
        templates = {
            "cmdr": ("<|START_OF_TURN_TOKEN|><|USER_TOKEN|>\n##Instruction\n", "<|END_OF_TURN_TOKEN|><|START_OF_TURN_TOKEN|><|CHATBOT_TOKEN|>"),
            "llama3": ("<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\nInstructions: ", "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"),
            "mistral": ("[INST] ", " [/INST]"),
            "alpaca": ("### Instruction:\n", "\n\n### Response:\n"),
            "chatml": ("<im_start>system\n You are a helpful assistant.<|im_end|>\n<|im_start|>user\n", "<|im_end|>\n<|im_start|>assistant\n"),
            "phi3": ("<|user|>\n", "<|end|>\n<|assistant|>"),
            "wizard": (" USER: "," ASSISTANT: ")
        }
        start_seq, end_seq = templates.get(self.model, templates["wizard"])
        return start_seq + instruction + content + end_seq

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
            
    def find_largest_context(self, chunk_size):
        context_set = [256, 512, 1024, 2048, 3072, 4096, 6144, 8192, 12288, 16384, 24576, 32768, 49152, 65536, 98304, 131072]
        index = bisect.bisect_right(context_set, chunk_size)
        return context_set[index] if index < len(context_set) else None

    def get_token_count(self, content):
        payload = {'prompt': content, 'genkey': self.genkey}
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
            
    def get_from_api(self, query="true_max_context_length"):
        try:
            response = requests.get(f"{self.api_url}/extra/{query}", headers=self.headers)
            if response.status_code == 200:
                return response.json().get('value', 0)
            else:
                print(f"API responded with status code {response.status_code}: {response.text}")
                return 0
        except Exception as e:
            print(f"Error in get_from_api: {e}")
            return 0
                
    def cleanup_content(self, content):
        if content is None:
            return ""
        content = ftfy.fix_text(content)
        content = re.sub(r'\n+', '\n', content)
        content = re.sub(r' +', ' ', content)
        return content.strip()





