**What does this do?**

llm-utility.py queries a koboldcpp API running an LLM and asks it for information on files. It starts in a directory specified by the user and finds any files in request caegories. If the ```--recursive``` flag is added it will crawl through all directories inside the specified as well. 

Documents:

It will attempt to parse any documents (txt, pdf, doc, etc) and it will send the content to the LLM as configured by the task configuration. The task will define how it is prompted and any parameters and how many chunks it will use. If set to 999 it will send the entire document in pieces with a prompt attached to each chunk in order -- useful for translated or editing a document. If num_chunks is 0 it will attempt to send the entire document in a single chunk which will only work if the document's token count is lower than the LLMs context size combined with its generation length. If num_chunks is in between those it will take always send the first chunk, then it will randomly select chunks from the document until it reaches num_chunks and stick them all together and send that wrapped in the prompt. This works for summaries and descriptions and analysis where the whole document doesn't need to be ingested. The default is set to 1 and will just grab the first chunk of size chunk_size at sentence limits and will query the LLM for Title, Topic, Subject, Author, Creator, and then ask for a suggested filename. 


Images:

It will send the images to the API one by one and ask the LLM to describe them. This requires a vision capable model with an mmproj file, like llava. Once the image is captioned it sends the caption to LLM as if the caption were a document and asks for a description and recommended filename.

*The llm-utility.py script does not alter any files.*

The other script, if you run it, will irrevocably and without questioning or confirming rename every file in the file_metadata.json created by the llm-utility to the recommended on by the LLM by using the path included. It will rename them ALL. **Do not run this on anything you care about without at least reading the json to see what it will rename.** 

**The script adds files info to the json every time you run it!** If you run it at directory 1, then again at directory 2, it will add on the file info from directory 2 to directory 1 and if you run the rename script it will rename all the files in both directories**

Installation

Install spacy and requirements:

```
pip install -U pip setuptools wheel
pip install -U spacy
python -m spacy download en_core_web_sm
pip install -r requirements.txt
```

Grab latest koboldcpp from repo:

  * https://github.com/LostRuins/koboldcpp

Grab the phi3 llava llm gguf and mmproj file:

* https://huggingface.co/xtuner/llava-phi-3-mini-gguf

Open koboldcpp executable, load phi3 and the mmproj, set options and when it is loaded type:

```
python llm-utility.py "c:\directory\to\crawl\with\no\ending\slash"
```

If you are want it to crawl through the entire directory tree add --recursive
Open the file-metadata.json file in notepad++ or chrome. It will look like this:

```json
{
  "carmack.txt": {
    "File": "carmack.txt",
    "Title": "Connect 2021: John Carmack",
    "Caption": "",
    "Creator": "John Carmack",
    "Author": "John Carmack",
    "Subject": "Virtual Reality",
    "Topic": "Presentation and Discussion of Virtual Reality Technologies and Advancements",
    "Filetype": "",
    "FullPath": "C:\\test\\carmack.txt",
    "PreviousPath": "",
    "PreviousName": "",
    "Size (KB)": 5,
    "Created": "2024-06-05T23:01:17.889296",
    "Modified": "2024-06-05T23:01:30.246009",
    "Category": "Document",
    "ProposedFilename": "connect_2021_john_carmack.mp4"
  },
  "image2.jpg": {
    "File": "image2.jpg",
    "Title": "A Man in a Purple Plaid Jacket Holding a Red Leash with a Dog on the Other End of the Leash",
    "Caption": "A man in a purple plaid jacket holding a red leash with a dog on the other end of the leash.",
    "Creator": "Anonymous",
    "Author": "Anonymous",
    "Subject": "Dogs",
    "Topic": "Pets",
    "Filetype": "",
    "FullPath": "C:\\test\\image2.jpg",
    "PreviousPath": "",
    "PreviousName": "",
    "Size (KB)": 98,
    "Created": "2024-07-08T18:47:29.460219",
    "Modified": "2024-07-08T18:47:21.701451",
    "Category": "Image",
    "ProposedFilename": "man_in_purple_jacket_and_dog.jpg"
  }
```

Now you can do whatever you want with that information.

But if you are feeling lucky you can have it rename all your files:

```
python .\file-renamer-script.py
```

It will then rename every document and image that it got info for and put in the file-metadata.json file. It will also update the field for PreviousName to be the previous filename.
It will hopefully disregard wrong proposed extensions.

*I TAKE NO RESPONSIBILITY FOR WHAT HAPPENS WHEN YOU RUN THIS*

It might rename all your files to be variations of swear words or something -- the LLM is the one calling the shots and who knows what it will do. At least check the filenames are sane before running the renamer.

Why did I choose these requirements?

* ftfy fixes unicode parsing errors that happened in the past (if a file was decoded and/or encoded wrong by some other program)
* natsort sorts files as the OS does, so that when you look at the metadata output it is not in a strange order making you hunt for files
* json-repir is needed because LLMs often will give you json that looks ok but doesn't parse
* spacy is used for fast and accurate sentence chunking
* tika is used to parse non-text files
  
Citations:

* https://spacy.io/
* https://github.com/josdejong/jsonrepair
* https://github.com/chrismattmann/tika-python
* https://github.com/SethMMorton/natsort
* 
@misc{speer-2019-ftfy,
  author       = {Robyn Speer},
  title        = {ftfy},
  note         = {Version 5.5},
  year         = 2019,
  howpublished = {Zenodo},
  doi          = {10.5281/zenodo.2591652},
  url          = {https://doi.org/10.5281/zenodo.2591652}
}


prompt_template.json was basically taken verbatim from https://github.com/aseichter2007/ClipboardConqueror/blob/main/inferenceInterface.js and converted into json format.
