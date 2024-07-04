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
        if not self.headers:
            print("Error: Unable to initialize headers")
            sys.exit(1)
        
        self.max_context_length = self.get_max_context()
        if self.max_context_length is None:
            print("Error: Unable to get max context length from API")
            sys.exit(1)

    def interrogate_image(self, image_path):
        try:
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            payload = {
                'image': base64_image,
                'model': 'clip',  # KoboldCpp uses CLIP for image interrogation
              
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
        print(f"Content length in chars before chunking: {len(cleaned_content)}")
        
        if num_chunks == 0:
            chunks = [cleaned_content]
        else:
            chunks = self.chunkify(cleaned_content, num_chunks=num_chunks)
        
        print(f"Number of chunks: {len(chunks)}")
        print(f"Total length of chars in chunks: {sum(len(chunk) for chunk in chunks)}")
        

    
        results = []
        for chunk in chunks:
            prompt = self.prompt_template(task.get('instruction'), content=chunk)
            tokens = self.get_token_count(prompt)
            print(f"Tokens in prompt: {tokens}")
            
            if tokens > self.max_context_length:
                print(f"Warning: Content exceeds max context length. Tokens: {tokens}, Max: {self.max_context_length}")
                prompt = prompt[:self.max_context_length]  # This is a naive truncation and might break the prompt 
                tokens = self.get_token_count(prompt) 
                
            max_length = self.find_largest_context(tokens) 
            payload = {
                'prompt': prompt,
                'max_length': tokens,
                #'max_context_length': self.max_context_length,
                **task.get('parameters', {})
            }
            
        result = self._call_api(payload)
        if result is None:
            print("API call failed or returned no results")
            return None
        return result
            
    def chunkify(self, content, sample_size=20, num_chunks=None):
        if num_chunks == 0:
            return [content]
        doc = self.nlp(content)
        sentences = list(doc.sents)
        #print(sentences)
        
        sample = sentences if len(sentences) <= sample_size else random.sample(sentences, sample_size)
        
        sample_text = " ".join(str(sent) for sent in sample)
        total_tokens = self.get_token_count(sample_text)
        avg_tokens_per_sentence = total_tokens / len(sample)
        
        try:
            sentences_per_chunk = max(1, int(self.chunk_size / avg_tokens_per_sentence))
        except:
            print("Average tokens not valid -- check API connectivity")
            chunks = [0,'error']

        chunks = [" ".join(str(sent) for sent in sentences[i:i + sentences_per_chunk]) 
                  for i in range(0, len(sentences), sentences_per_chunk)]
        
        if num_chunks > 0:
            if num_chunks > len(chunks):
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
            print(f"Sending payload to API: {payload}")  # Debug print
            response = requests.post(f"{self.api_url}/v1/generate/", json=payload, headers=self.headers)
            print(f"API response status code: {response.status_code}")  # Debug print
            print(f"API response content: {response.text}")  # Debug print
            if response.status_code == 200:
                self.generated = True
                poll_thread.join()
                result = response.json()
                if 'results' in result and len(result['results']) > 0:
                    return result['results'][0].get('text')
                else:
                    print(f"Unexpected API response structure: {result}")
                    return None
            elif response.status_code == 503:
                print("Server is busy; please try again later.")
                return None
            else:
                print(f"API responded with status code {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"Error communicating with API: {str(e)}")
            return None
        finally:
            self.generated = True  # Ensure the polling thread stops

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

        if (chunk_size + 500) <= self.max_context_length:
            gen_length = [num for num in context_set if chunk_size <= num <= self.max_context_length]
            
            if not gen_length:
                return None
            return gen_length        
            
        
        else:
            return None
            
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
            
    def get_max_context(self):
        payload = {'genkey': self.genkey}
        try:
            response = requests.get(f"{self.api_url}/extra/true_max_context_length", headers=self.headers)
            if response.status_code == 200:
                return response.json().get('value', 0)
                
            else:
                print(f"API responded with status code {response.status_code}: {response.text}")
                return
        except Exception as e:
            print(f"Error in get_from_api: {e}")
            return 
                
    def cleanup_content(self, content):
        if content is None:
            return ""
        content = ftfy.fix_text(content)
        content = re.sub(r'\n+', '\n', content)
        content = re.sub(r' +', ' ', content)
        return content.strip()





