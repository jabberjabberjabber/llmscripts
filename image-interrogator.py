import argparse
import json
import os
from tasker import FileCrawler
from llmer import LLMProcessor

class ImageInterrogator:
    def __init__(self, api_url, password, model):
        self.llm_processor = LLMProcessor(api_url, password, model, chunk_size=1)

    def interrogate_images(self, directory):
        file_crawler = FileCrawler()
        file_list = file_crawler.crawl(directory, recursive=True, categories=['image'])

        results = {}

        for category, files in file_list.items():
            for file_info in files:
                file_path = file_info['path']
                caption = self.llm_processor.interrogate_image(file_path)
                if caption:
                    results[file_path] = {
                        'caption': caption,
                        'metadata': file_info['metadata']
                    }
                    print(f"Interrogated: {file_path}")
                else:
                    print(f"Failed to interrogate: {file_path}")

        return results

    def save_results(self, results, output_file):
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Interrogate images in filesystem')
    parser.add_argument('--api-url', default='http://localhost:5001/api', help='the URL of the LLM API')
    parser.add_argument('--password', default='', help='server password')
    parser.add_argument('--model', default='clip', help='model to use for image interrogation')
    parser.add_argument('directory', help='Directory to search for images')
    parser.add_argument('--output', default='image_interrogation_results.json', help='Output JSON file')
    args = parser.parse_args()

    interrogator = ImageInterrogator(args.api_url, args.password, args.model)
    results = interrogator.interrogate_images(args.directory)
    interrogator.save_results(results, args.output)

if __name__ == "__main__":
    main()
