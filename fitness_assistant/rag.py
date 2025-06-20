from google import genai
import injest
from time import time
import os
import re
import logging
import json
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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



def get_gemini_client():
    """Initialize Gemini client"""
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        logger.info("Gemini client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        raise

def calculate_gemini_cost(prompt_tokens: int,
                          candidate_tokens: int,
                          input_cost_per_token: float = 0.075 / 1_000_000,
                          output_cost_per_token: float = 0.30 / 1_000_000
                          ) -> float:
    """
    Calculates the estimated cost of a Gemini API call using fixed rates for Gemini 1.5 Flash.
    (Rates: Input = $0.075/M tokens, Output = $0.30/M tokens)

    Args:
        prompt_tokens (int): The number of tokens in the input prompt.
        candidate_tokens (int): The number of tokens in the generated response (completion).

    Returns:
        float: The estimated total cost in USD.
    """
    # Rates for Gemini 1.5 Flash (as of recent updates), per single token
    # Always verify these with the official Google AI for Developers pricing page!
    
    total_cost = (prompt_tokens * input_cost_per_token) + \
                 (candidate_tokens * output_cost_per_token)

    return total_cost

def llm_gemini(prompt, model="gemini-1.5-flash"):
    """Get response from Gemini"""
    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=model, 
            contents=prompt
        )
        prompt_tokens = response.usage_metadata.prompt_token_count
        total_tokens = response.usage_metadata.total_token_count
        candidate_tokens = response.usage_metadata.candidates_token_count
       
        tokens_stats = {
            "prompt_tokens": prompt_tokens,
            "total_tokens": total_tokens,
            "completion_tokens": candidate_tokens
            
        }
        

        # gemini_cost = (prompt_tokens * 0.00035 + completion_tokens * 0.00105) / 1000
        
        logger.info(f"Gemini response received for model {model}")
        return response.text, tokens_stats
    except Exception as e:
        logger.error(f"Gemini request failed: {e}")
        raise



def evaluate_relevance(question, answer, model="gemini-2.0-flash"):
    """Evaluate answer relevance using Gemini-1.5-flash"""
    prompt_template = """
        You are an expert judge evaluating a generated answer in a Question-Answering (QA) system. You do NOT have access to a reference answer.

        You are given:
        - A generated question
        - A generated answer

        Your task is to assess whether the generated answer is appropriate, coherent, and directly relevant to the question.

        Provide the output as a pure JSON string, without wrapping it in Markdown code fences, code blocks, or any other formatting.
        Example output:

        {{
        "Relevance": "RELEVANT" | "PARTIALLY_RELEVANT" | "NON_RELEVANT",
        "Explanation": "Brief explanation of your reasoning"
        }}

        Guidelines:
        - "RELEVANT": The answer is coherent, correct, and directly answers the question.
        - "PARTIALLY_RELEVANT": The answer is partially correct or vague, or it omits key information.
        - "NON_RELEVANT": The answer does not answer the question, is off-topic, or is factually incorrect.

        Now evaluate:

        Question: {question} 
        Generated Answer: {answer_llm}
        """.strip()
        
    
    prompt = prompt_template.format(question=question, answer_llm=answer)
    evaluation, tokens_stats = llm_gemini(prompt, model=model)
    
    
    try:
        json_eval = json.loads(evaluation)
        return json_eval, tokens_stats
    except json.JSONDecodeError as e:
        results = {
            "Relevance": "UNKNOWN",
            "Explanation": f"Failed to parse evaluation: {str(e)}"
        }
        return results, tokens_stats
    


def rag(query, model="gemini-1.5-flash"):
    t0 = time()
    
    search_results = minsearch_search_improved(query)
    prompt = build_prompt(query, search_results)
    answer, tokens_stats = llm_gemini(prompt, model=model)
    gemini_cost_rag = calculate_gemini_cost(
        prompt_tokens=tokens_stats["prompt_tokens"],
        candidate_tokens=tokens_stats["completion_tokens"]
    )
    
    evaluation, rel_tokens_stats = evaluate_relevance(question=query,
                       answer=answer, model="gemini-2.0-flash")
    gemini_cost_eval = calculate_gemini_cost(
        prompt_tokens=rel_tokens_stats["prompt_tokens"],
        candidate_tokens=rel_tokens_stats["completion_tokens"],
        input_cost_per_token = 0.10 / 1_000_000,
        output_cost_per_token = 0.40 / 1_000_000
        
    )
    gemini_cost = gemini_cost_rag + gemini_cost_eval
    
    t1 = time()
    response_time = t1 - t0
    
    answer_data = {
        "answer": answer,
        "model_used": model,
        "response_time": response_time,
        "relevance": evaluation["Relevance"],
        "relevance_explanation": evaluation["Explanation"],
        "prompt_tokens": tokens_stats["prompt_tokens"],
        "completion_tokens": tokens_stats["completion_tokens"],
        "total_tokens": tokens_stats["total_tokens"],
        "eval_prompt_tokens": rel_tokens_stats["prompt_tokens"],
        "eval_completion_tokens": rel_tokens_stats["completion_tokens"],
        "eval_total_tokens": rel_tokens_stats["total_tokens"],
        "gemini_cost": gemini_cost,
    }
    
    
    
 
    return answer_data





