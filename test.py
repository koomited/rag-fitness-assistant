import requests

question = "How to get a flat stomach?"

url = "http://localhost:5000/ask"
data = {
    "question": question
    }
response = requests.post(url, json=data).json()
print(response)

feedback_url = "http://localhost:5000/feedback"
feedback_data = {
    "conversation_id": response["conversation_id"],
    "feedback": 1  # Positive feedback
}
feedback_response = requests.post(feedback_url, json=feedback_data)
print(feedback_response.json())