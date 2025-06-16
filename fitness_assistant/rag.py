
from google import genai

import injest

import os
os.environ["GEMINI_API_KEY"] = "AIzaSyBPcFwBMINWQa3fWGh0fhkWx6hU9uR0NB0"


client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

index = injest.load_index()


def search(query, boost):
    """Perform a search using the minsearch index with boosting"""
    results = index.search(
        query=query,
        boost_dict=boost,
        num_results=10
    )
    return results



def minsearch_search_improved(query):
    """Perform a search using the minsearch index with optimized boosting"""

    boost = {'body_part': 0.947771590052861,
            'exercise_name': 2.8439224585464493,
            'instructions': 0.6987228015703881,
            'muscle_groups_activated': 0.49261344050772715,
            'type': 2.587600420079811,
            'type_of_activity': 0.3898333128794963,
            'type_of_equipment': 1.234288967556835
            }
    return search(query=query, boost=boost)



prompt_template = """
You're a fitness instructor. Answer the QUESTION based on the CONTEXT from our exercises database.
Use only the facts from the CONTEXT when answering the QUESTION.

QUESTION: {question}

CONTEXT: 
{context}
""".strip()

entry_template = """
    'exercise_name': {exercise_name}
    'type_of_activity': {type_of_activity}
    'type_of_equipment': {type_of_equipment}
    'body_part':  {body_part}
    'type' : {type}
    'muscle_groups_activated': {muscle_groups_activated}
    'instructions': {instructions}

    """.strip()


def build_prompt(query, search_results):


    context = ""

    for doc in search_results:
        context = context + entry_template.format(**doc) + "\n\n"

    prompt = prompt_template.format(question=query, context=context).strip()
    return prompt



def llm(prompt, model = "gemini-1.5-flash"):
    """
    Call the LLM with the given prompt and model.
    Args:
        prompt (str): The prompt to send to the LLM.
        model (str): The model to use for generating content.
    Returns:
        str: The generated content from the LLM.
    """
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )

    return response.text


def rag(query, model="gemini-1.5-flash"):
    search_results = minsearch_search_improved(query)
    prompt = build_prompt(query, search_results)
    answer = llm(prompt, model=model)
    return answer





