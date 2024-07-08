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

Grab the largest gemma2-9b GGUF that can fit in your VRAM - 20%:

* https://huggingface.co/bartowski/gemma-2-9b-it-GGUF

Open koboldcpp executable, load gemma2, set options and when it is loaded type:

```
python extract-metadata.py "c:\directory\to\crawl\with\no\ending\slash"
```
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
