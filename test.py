import requests

question = "How to get a flat stomach?"

url = "http://localhost:5000/ask"
data = {
    "question": question
    }
response = requests.post(url, json=data).json()
print(response)