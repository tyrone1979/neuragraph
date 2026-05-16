
from langchain_core.prompts import ChatPromptTemplate
from data.data_load import load_parser
from comparison.metrics import MetricsCalculation
import json

labels = ["Chemical", "Disease"]

def convert_to_str(text):
    text= text.replace(" ", "")
    return text.replace("'", "")

def create_entity_pair(expected_entities) -> list:
    heads = []
    tails = []
    if 'Chemical' in expected_entities:
        heads = expected_entities['Chemical']
    if 'Disease' in expected_entities:
        tails = expected_entities['Disease']
    pairs = []
    for head in heads:
        for tail in tails:
            pairs.append({"head": head, "tail": tail})
    return  pairs

def entity_link(result,pair,entity_link):
    if result == '$':
        __result__ = (entity_link[pair['head']], entity_link[pair["tail"]])
        return __result__
    return ()


def relation_verify(text,head,tail):
    from langchain_ollama import ChatOllama
    model = ChatOllama(
        model="mistral",  # ollama list 里看到的模型名
        base_url="localhost",  # 注意带 /v1
        temperature=0
    )
    template = ChatPromptTemplate(
        [("system", "You are a biomedical relation specialist."),
         ("human", """
            Refer to below article, please give answer '$' or '~' only based on below conditions:
            **Assumptions**:
            1.1 if 'patient had/exhibited {tail} on the Xth day of {head} treatment', please do not use it and find other reason.
            1.2 if 'difference did not reach statistical significance compared to groups' appeared, please do not use it and find other reason.
            **Conditions**:
            1. if the article gave the conclusion that the interaction between {head} and another chemical induce {tail}, or {head} induce {tail}, answer '$'
            2. else if the article mentioned {tail} was reported in the percentage of patients because of {head}, answer '$'
            3. else the article mentioned '{head} is  mediating/attenuating {tail}, answer '~'
            4. else if {head} and {tail} have no relationship, answer '~'.
            DO NOT output any other message.
            **article**:
             {text}""")]
    )
    base_dict = {'text': text,"head": head, "tail": tail}
    prompt_value = template.invoke(base_dict)
    ai_msg = model.invoke(prompt_value)
    if ai_msg and hasattr(ai_msg, 'content'):
        result = convert_to_str(ai_msg.content)
        return result
    return "~"


if __name__ == '__main__':
    parser = load_parser("CDR", "dev.txt")
    articles = parser.get_articles()
    expected_re = []
    results = []
    for article in articles:
        pairs=create_entity_pair(article.expected_entities)
        expected_re.append(article.expected_relations)
        for pair in pairs:
            head, tail = pair['head'], pair['tail']
            result=relation_verify(article.text,head,tail)
            results.append(entity_link(result,pair,article.entity_link))

    MetricsCalculation.calculate(expected_re, results)