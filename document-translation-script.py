import os
import json
from datetime import datetime
from langdetect import detect
from llmprocessor import LLMProcessor, TaskProcessor, FileUtils, FileCrawler

class DocumentTranslator:
    def __init__(self, input_dir, output_dir, log_file, api_url, password, task_config_path):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.log_file = log_file
        self.llm_processor = LLMProcessor(api_url, password)
        self.task_processor = TaskProcessor(self.llm_processor, task_config_path)
        self.file_crawler = FileCrawler()
        self.log = []

    def is_english(self, text):
        try:
            return detect(text) == 'en'
        except:
            return False

    def translate_document(self, file_path):
        content = FileUtils.read_file_content(file_path)
        if not self.is_english(content):
            file_info = {'path': file_path}
            result = self.task_processor.process_tasks(file_info, content, ['translate'])
            return result.get('translate')
        return None

    def save_translated_document(self, original_path, translated_content):
        relative_path = os.path.relpath(original_path, self.input_dir)
        new_path = os.path.join(self.output_dir, relative_path)
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        with open(new_path, 'w', encoding='utf-8') as f:
            f.write(translated_content)
        return new_path

    def process_directory(self):
        file_list = self.file_crawler.crawl(self.input_dir, recursive=True)
        for category, files in file_list.items():
            if category == 'document':  # Only process files categorized as documents
                for file_info in files:
                    self.process_file(file_info['path'])
            else:
                for file_info in files:
                    self.log_skipped_file(file_info['path'], f"Not a document (category: {category})")

    def process_file(self, file_path):
        action = {"timestamp": datetime.now().isoformat(), "action": "process_file", "file": file_path}
        translated_content = self.translate_document(file_path)
        if translated_content:
            new_path = self.save_translated_document(file_path, translated_content)
            action["result"] = "translated"
            action["new_file"] = new_path
        else:
            action["result"] = "skipped"
            action["reason"] = "already in English or translation failed"
        self.log.append(action)

    def log_skipped_file(self, file_path, reason):
        action = {
            "timestamp": datetime.now().isoformat(),
            "action": "process_file",
            "file": file_path,
            "result": "skipped",
            "reason": reason
        }
        self.log.append(action)

    def save_log(self):
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(self.log, f, indent=2)

    def run(self):
        self.process_directory()
        self.save_log()

if __name__ == "__main__":
    input_dir = "./test"
    output_dir = "./translated"
    log_file = "translation_log.json"
    api_url = "http://172.16.0.219:5001/api"
    password = "poop"
    task_config_path = "task_config.json"

    translator = DocumentTranslator(input_dir, output_dir, log_file, api_url, password, task_config_path)
    translator.run()
