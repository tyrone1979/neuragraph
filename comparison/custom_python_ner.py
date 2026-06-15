from flair.models import SequenceTagger
import pathlib

from flair.data import Sentence
from langchain_core.prompts import ChatPromptTemplate
from service.dataset.parsers import load_parser
from comparison.metrics import MetricsCalculation
import json

labels=["Chemical","Disease"]
MODEL_DIR = pathlib.Path(__file__).resolve().parent.parent / "models" / "hunflair2-ner" / "pytorch_model.bin"
flair_tagger = SequenceTagger.load(str(MODEL_DIR))

def _convert_to_list(raw: str):
    try:
         return json.loads(raw)
    except json.JSONDecodeError as e:
                entities = raw.split('\n')
                return entities


def ner_task(sentence):
    sentence = Sentence(sentence)
    flair_tagger.predict(sentence)
    __result__={}

    for label in labels:
        __result__[label]=[]
        for entity in sentence.get_spans('ner'):
            if entity.tag==label:
                __result__[label].append(entity.text)

    return __result__

def sentence_split(text):
    from langchain_ollama import ChatOllama
    model = ChatOllama(
        model="mistral",  # ollama list 里看到的模型名
        base_url="localhost",  # 注意带 /v1
        temperature=0
    )
    template = ChatPromptTemplate(
        [("system", "You are an English-text sentence splitter."),
         ("human", """
         Task: split the following biomedical abstract into complete sentences according to English grammar and punctuation.
            Rules:
            - Keep all content, including braces, do not remove or alter them.
            - Output **only** a JSON array of strings, one sentence per element.
            - Do **not** add any explanations or extra text.
            - **Do not add any introductory sentences like "Here is the output..."
            
            Biomedical abstract:
            {text}""")]
    )
    base_dict={'text':text}
    prompt_value = template.invoke(base_dict)
    ai_msg = model.invoke(prompt_value)
    if ai_msg and hasattr(ai_msg, 'content'):
        result = ai_msg.content
        out = _convert_to_list(result)
        return out

if __name__ == '__main__':
    parser=load_parser("CDR","dev.txt")
    articles=parser.get_articles()
    expected_entities=[]
    results=[]
    for article in articles:
        expected_entities.append(article.expected_entities)
        sentences=sentence_split(article.text)
        for sentence in sentences:
            results.append(ner_task(sentence))

    MetricsCalculation.calculate(expected_entities,results)