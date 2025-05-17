import os
import json
import sqlite3
from flask import Flask, render_template, jsonify, request, session
from flask_cors import CORS
import hashlib
import time
import hmac
import base64

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get("SESSION_SECRET", "masterquiz_telegram_webapp_secret")

# Telegram Bot Token (same as in main.py)
BOT_TOKEN = "8184215515:AAEVINsnkj_fTBbxZfBpvqZtUCsNj2kvwjo"

# Function to validate Telegram WebApp data
def validate_telegram_webapp(init_data):
    if not init_data:
        return False, None
    
    # Parse the init data
    data_dict = {}
    for item in init_data.split('&'):
        if '=' in item:
            key, value = item.split('=', 1)
            data_dict[key] = value
    
    # Check if hash is present
    if 'hash' not in data_dict:
        return False, None
    
    # Extract hash
    received_hash = data_dict.pop('hash')
    
    # Sort the data
    data_check_string = '\n'.join([f"{k}={v}" for k, v in sorted(data_dict.items())])
    
    # Calculate secret key
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    
    # Calculate hash
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    # Verify hash
    if calculated_hash != received_hash:
        return False, None
    
    # Get user data
    user_data = None
    if 'user' in data_dict:
        try:
            user_data = json.loads(data_dict['user'])
        except:
            pass
    
    return True, user_data

# Function to get tests for a user
def get_user_tests(user_id):
    try:
        with open('../user_tests.json', 'r', encoding='utf-8') as f:
            tests_data = json.load(f)
            return tests_data.get(str(user_id), [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

# Main route for the web app
@app.route('/')
def index():
    return render_template('index.html')

# API endpoint to validate Telegram user and get their tests
@app.route('/api/validate', methods=['POST'])
def validate_user():
    init_data = request.form.get('initData')
    is_valid, user_data = validate_telegram_webapp(init_data)
    
    if not is_valid or not user_data:
        return jsonify({
            'success': False,
            'message': 'Invalid authentication data'
        }), 401
    
    # Store user data in session
    session['user_id'] = user_data.get('id')
    session['username'] = user_data.get('username')
    session['first_name'] = user_data.get('first_name')
    
    return jsonify({
        'success': True,
        'user': user_data
    })

# API endpoint to get tests for the authenticated user
@app.route('/api/tests', methods=['GET'])
def get_tests():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({
            'success': False,
            'message': 'User not authenticated'
        }), 401
    
    tests = get_user_tests(user_id)
    
    return jsonify({
        'success': True,
        'tests': tests
    })

# API endpoint to get a specific test
@app.route('/api/tests/<test_id>', methods=['GET'])
def get_test(test_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({
            'success': False,
            'message': 'User not authenticated'
        }), 401
    
    tests = get_user_tests(user_id)
    
    # Find the test with the matching ID
    test = None
    for t in tests:
        if str(t.get('id', '')) == str(test_id):
            test = t
            break
    
    if not test:
        return jsonify({
            'success': False,
            'message': 'Test not found'
        }), 404
    
    return jsonify({
        'success': True,
        'test': test
    })

# API endpoint to submit test answers
@app.route('/api/submit_test', methods=['POST'])
def submit_test():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({
            'success': False,
            'message': 'User not authenticated'
        }), 401
    
    data = request.json
    test_id = data.get('test_id')
    answers = data.get('answers', [])
    
    # Get the test
    tests = get_user_tests(user_id)
    test = None
    for t in tests:
        if str(t.get('id', '')) == str(test_id):
            test = t
            break
    
    if not test:
        return jsonify({
            'success': False,
            'message': 'Test not found'
        }), 404
    
    # Calculate score
    correct_count = 0
    total_questions = len(test.get('questions', []))
    
    for i, question in enumerate(test.get('questions', [])):
        if i < len(answers) and answers[i] == question.get('correct_option'):
            correct_count += 1
    
    score = correct_count / total_questions if total_questions > 0 else 0
    percentage = score * 100
    
    # TODO: Save results to database (would need to integrate with the bot's database)
    
    return jsonify({
        'success': True,
        'score': {
            'correct': correct_count,
            'total': total_questions,
            'percentage': percentage
        }
    })

if __name__ == "__main__":
    # Get port from environment variable (Railway sets this)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
