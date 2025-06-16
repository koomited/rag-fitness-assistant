#!/usr/bin/env python
# coding: utf-8

import pandas as pd


# # Ingestion

df = pd.read_csv('../data/data.csv')
df.head()


import minsearch


# In[4]:


documents = df.to_dict(orient='records')


# In[5]:


index = minsearch.Index(
    text_fields=['exercise_name', 'type_of_activity', 'type_of_equipment', 'body_part',
       'type', 'muscle_groups_activated', 'instructions'],
    keyword_fields=["ID"]
)


# In[6]:


index.fit(documents)


# In[7]:


query = 'give me a workout for my legs'


# In[8]:


index.search(query, num_results=10)


# # Rag flow

# In[9]:


from google import genai


# In[10]:


import os
os.environ["GEMINI_API_KEY"] = "AIzaSyBPcFwBMINWQa3fWGh0fhkWx6hU9uR0NB0"


# In[11]:


client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# In[12]:


def search(query):
    boost = {}

    results = index.search(
        query=query,
        boost_dict=boost,
        num_results=10
    )

    return results


# In[13]:


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


# In[14]:


def build_prompt(query, search_results):


    context = ""

    for doc in search_results:
        context = context + entry_template.format(**doc) + "\n\n"

    prompt = prompt_template.format(question=query, context=context).strip()
    return prompt


# In[15]:


search_results = search(query)
prompt = build_prompt(query, search_results)


# In[16]:


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



# In[17]:


def rag(query):
    search_results = search(query)
    prompt = build_prompt(query, search_results)
    answer = llm(prompt)
    return answer


# ## Retrieval evaluation

# In[18]:


prompt1_template = """

You emulate a user of our fitness assistant application. 
Formulate 5 questions a user might ask based on the provided exercise. 
Make the questions specific to the exercise. 
The record should contain the answers to the questions, and the questions should be complete and not too short.
Use as few words as possible from the record.

The record:

exercise_name: {exercise_name} 
type_of_activity: {type_of_activity}
type_of_equipment: {type_of_equipment}
body_part: {body_part} type: {type} 
muscle_groups_activated: {muscle_groups_activated} 
instructions: {instructions}

Provide the output as a pure JSON string, without wrapping it in Markdown code fences, code blocks, or any other formatting.
Example output:

{{"questions": ["question1", "question2", "question3", "question4", "question5"]}}
Don't provide answers, just questions.
""".strip()


# In[20]:


prompt = prompt1_template.format(**documents[0])


# In[21]:


questions = llm(prompt)


# In[22]:


questions


# In[23]:


import json


# In[24]:


json.loads(questions)


# In[29]:


def generate_questions(doc):
    prompt = prompt1_template.format(**doc)

    response = llm(prompt)

    json_response = response
    return json_response


# In[30]:


from tqdm.auto import tqdm   


# In[31]:


results = {}


# In[ ]:


for doc in tqdm(documents):
    doc_id = doc['ID']
    if doc_id in results:
        continue
    questions_raw = generate_questions(doc)
    questions = json.loads(questions_raw.strip())
    results[doc_id] = questions['questions']


# In[58]:


final_results = []

for doc_id, questions in results.items():
    for q in questions:
        final_results.append((doc_id, q))


# In[59]:


final_results[0]


# In[62]:


df_results= pd.DataFrame(final_results, columns=['id', 'question'])


# In[63]:


df_results.to_csv('../data/ground-trunth-retrieval.csv', index=False)


# In[64]:


get_ipython().system('head ../data/ground-trunth-retrieval.csv')


# In[ ]:





# In[32]:


df_questions = pd.read_csv('../data/ground-trunth-retrieval.csv')


# In[34]:


ground_truth = df_questions.to_dict(orient='records')


# In[35]:


ground_truth[0]


# In[36]:


def hit_rate(relevance_total):
    """Calculate the hit rate"""
    hits = sum([any(r) for r in relevance_total])
    return hits / len(relevance_total)


# In[37]:


def mrr(relevance_total):
    """Calculate the Mean Reciprocal Rank (MRR)"""
    ranks = []
    for relevance in relevance_total:
        try:
            rank = 1 / (relevance.index(True) + 1)
        except ValueError:
            rank = 0
        ranks.append(rank)
    return sum(ranks) / len(ranks)


# In[38]:


def minsearch_search(query):
    """Perform a search using the minsearch index"""
    boost = {}
    results = index.search(
        query=query,
        boost_dict=boost,
        num_results=10
    )
    return results


# In[39]:


def evaluate_search(ground_truth, search_fn):
    """Evaluate the search results"""
    relevance_total = []
    for q in tqdm(ground_truth):
       doc_id = q["id"]
       results = search_fn(q)
       relevance = [d["ID"] == doc_id for d in results]
       relevance_total.append(relevance)
    return {
        "hit_rate": hit_rate(relevance_total),
        "mrr": mrr(relevance_total)
    }


# In[40]:


evaluate_search(ground_truth, lambda q: minsearch_search(query=q["question"]))


# # Finding the best parameters

# In[42]:


df_validation = df_questions[:100]

df_test = df_questions[100:]


# In[43]:


from hyperopt import fmin, tpe, hp, Trials, STATUS_OK


# In[44]:


from hyperopt.pyll import scope


# ## Finding the best parameters

# In[45]:


gt_val = df_validation.to_dict(orient='records')
gt_test = df_test.to_dict(orient='records')


# In[46]:


evaluate_search(gt_val, lambda q: minsearch_search(query=q["question"]))


# In[47]:


def minsearch_search_boosted(query, boost):
    """Perform a search using the minsearch index with boosting"""
    results = index.search(
        query=query,
        boost_dict=boost,
        num_results=10
    )
    return results


# In[48]:


param_ranges = {
    "exercise_name": hp.uniform("exercise_name", 0, 3),
    "type_of_activity": hp.uniform("type_of_activity", 0, 3),
    "type_of_equipment": hp.uniform("type_of_equipment", 0, 3),
    "body_part": hp.uniform("body_part", 0, 3),
    "type": hp.uniform("type", 0, 3),
    "muscle_groups_activated": hp.uniform("muscle_groups_activated", 0, 3),
    "instructions": hp.uniform("instructions", 0, 3)
}


# In[49]:


def objective(boost_params):
    def search_function(q):
        return minsearch_search_boosted(
            query=q["question"],
            boost=boost_params
        )
    results = evaluate_search(gt_val, search_function)
    return -results["mrr"]



# In[50]:


optim_params = fmin(objective,
    space=param_ranges,
    algo=tpe.suggest,
    max_evals=20,
    trials=Trials()
)


# In[51]:


optim_params


# In[52]:


evaluate_search(ground_truth, lambda q: minsearch_search_boosted(query=q["question"], boost=optim_params))


# In[53]:


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
    return minsearch_search_boosted(query=query, boost=boost)


# In[54]:


evaluate_search(ground_truth, lambda q: minsearch_search_improved(query=q["question"]))


# # RAG Evaluation

# In[55]:


def rag(query, model="gemini-1.5-flash"):
    search_results = minsearch_search_improved(query)
    prompt = build_prompt(query, search_results)
    answer = llm(prompt, model=model)
    return answer


# In[56]:


prompt2_template = """
You are an expert judge evaluating a generated answer in a Question-Answering (QA) system. You do NOT have access to a reference answer.

You are given:
- A generated question
- A generated answer

Your task is to assess whether the generated answer is appropriate, coherent, and directly relevant to the question.

Provide the output as a pure JSON string, without wrapping it in Markdown code fences, code blocks, or any other formatting.
Example output:

{{
  "evaluation": "RELEVANT" | "PARTIALLY_RELEVANT" | "NON_RELEVANT",
  "explanation": "Brief explanation of your reasoning"
}}

Guidelines:
- "RELEVANT": The answer is coherent, correct, and directly answers the question.
- "PARTIALLY_RELEVANT": The answer is partially correct or vague, or it omits key information.
- "NON_RELEVANT": The answer does not answer the question, is off-topic, or is factually incorrect.

Now evaluate:

Question: {question} 
Generated Answer: {answer_llm}
""".strip()


# In[57]:


record = ground_truth[0]


# In[58]:


question = record['question']
answer_llm = rag(question)
prompt2 = prompt2_template.format(question=question, answer_llm=answer_llm)
print(prompt2)


# In[59]:


df_sample = df_questions.sample(200)
sample = df_sample.to_dict(orient='records')


# In[143]:


import json


# In[60]:


evaluations = []


# In[61]:


for rec in tqdm(sample):
    id = rec['id']
    # if id in evaluations:
    #     continue
    question = rec['question']

    answer_llm = rag(question)
    # Generate the evaluation prompt
    prompt = prompt2_template.format(question=question, answer_llm=answer_llm)
    evaluation = json.loads(llm(prompt))
    evaluations.append((id, rec, answer_llm, evaluation["evaluation"], evaluation["explanation"]))


# In[63]:


evaluations[0]
df_evaluations = pd.DataFrame(evaluations, columns=['id', 'record', 'answer_llm', 'evaluation', 'explanation'])


# In[64]:


df_evaluations.head()


# In[71]:


# df_evaluations["question"] = df_evaluations["record"].apply(lambda x: x['question'])
# df_evaluations["id"] = df_evaluations["record"].apply(lambda x: x['id'])
# df_evaluations = df_evaluations.drop(columns=['record'])
df_evaluations.rename(columns={'evaluation': 'relevance'}, inplace=True)
df_evaluations.to_csv('../data/ground-truth-evaluation.csv', index=False)
get_ipython().system('head ../data/ground-truth-evaluation.csv')


# In[72]:


df_evaluations.head()


# In[74]:


df_evaluations.relevance.value_counts(normalize=True)


# In[89]:


evaluation_gemini20flash = []


# In[91]:


for rec in tqdm(sample):
    id = rec['id']
    # if id in evaluations:
    #     continue
    question = rec['question']

    answer_llm = rag(question, model="gemini-2.0-flash")
    # Generate the evaluation prompt
    prompt = prompt2_template.format(question=question, answer_llm=answer_llm)
    evaluation = json.loads(llm(prompt))
    # print(evaluation["evaluation"], evaluation["explanation"])
    evaluation_gemini20flash.append((id, rec, answer_llm, evaluation["evaluation"], evaluation["explanation"]))


# In[92]:


df_evaluations_gemini20flash = pd.DataFrame(evaluation_gemini20flash, columns=['id', 'record', 'answer_llm', 'evaluation', "explanation"])
df_evaluations_gemini20flash.rename(columns={'evaluation': 'relevance'}, inplace=True)
df_evaluations_gemini20flash["question"] = df_evaluations_gemini20flash["record"].apply(lambda x: x['question'])
df_evaluations_gemini20flash["id"] = df_evaluations_gemini20flash["record"].apply(lambda x: x['id'])
df_evaluations_gemini20flash = df_evaluations_gemini20flash.drop(columns=['record'])
df_evaluations_gemini20flash.to_csv('../data/ground-truth-evaluation-gemini20flash.csv', index=False)
df_evaluations_gemini20flash.head()


# In[93]:


get_ipython().system('head ../data/ground-truth-evaluation-gemini20flash.csv')


# In[ ]:




