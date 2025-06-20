from flask import Flask, request, jsonify
import uuid
from rag import rag  
import db

app = Flask(__name__)

@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.get_json()
    question = data.get('question')
    
    if not question:
        return jsonify({'error': 'Question is required'}), 400
    
    # Generate a unique conversation ID
    conversation_id = str(uuid.uuid4())
    
    try:
        # Invoke the RAG function with the question
        answer_data = rag(question)
        
        # db.save_conversation(
        #             question=question,
        #             answer=answer,
        #             model_used="gemini-1.5-flash",
        #             response_time=result["response_time"],
        #             relevance=result["relevance"],
        #             relevance_explanation=result["relevance_explanation"],
        #             prompt_tokens=result["prompt_tokens"],
        #             completion_tokens=result["completion_tokens"],
        #             gemini_cost=result["gemini_cost"]
        #         )  # Save conversation to the database
        
        # Return the answer and conversation ID
        
        db.save_conversation(
                            conversation_id=conversation_id,
                            question=question,
                             answer = answer_data.get("answer"), 
                             model_used=answer_data["model_used"], 
                             response_time=answer_data["response_time"], 
                            relevance=answer_data["relevance"], 
                            relevance_explanation=answer_data["relevance_explanation"],
                            prompt_tokens=answer_data["prompt_tokens"], 
                            completion_tokens= answer_data["completion_tokens"],
                            gemini_cost= answer_data["gemini_cost"])
        return jsonify({
            'conversation_id': conversation_id,
            'question': question,
            'answer_data': answer_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error processing question: {str(e)}'}), 500

@app.route('/feedback', methods=['POST'])
def submit_feedback():
    # Get the conversation ID and feedback from the request
    data = request.get_json()
    conversation_id = data.get('conversation_id')
    feedback = data.get('feedback')
    
    if not conversation_id or feedback not in [-1, 1]:
        return jsonify({'error': 'Valid conversation_id and feedback (+1 or -1) are required'}), 400
    
    db.save_feedback(conversation_id=conversation_id,
                     feedback=feedback
                     )
    # Acknowledge receiving feedback (database storage to be implemented later)
    return jsonify({
        'message': f'Received feedback {feedback} for conversation {conversation_id}'
    }), 200

if __name__ == '__main__':
    app.run(debug=True)