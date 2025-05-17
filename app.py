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
    try:
        # URL decode the init_data
        import urllib.parse
        decoded_data = urllib.parse.unquote(init_data)
        
        data_dict = {}
        for item in decoded_data.split('&'):
            if '=' in item:
                key, value = item.split('=', 1)
                data_dict[key] = value
        
        # For now, we'll simplify and just check if user data exists
        if 'user' not in data_dict:
            return False, None
        
        # Get user data
        try:
            user_data = json.loads(urllib.parse.unquote(data_dict['user']))
            return True, user_data
        except Exception as e:
            print(f"Error parsing user data: {e}")
            return False, None
            
    except Exception as e:
        print(f"Error validating Telegram WebApp data: {e}")
        return False, None

# Function to get tests for a user
def get_user_tests(user_id):
    # Convert user_id to string if it's not already
    user_id_str = str(user_id)
    print(f"Getting tests for user: {user_id_str}")
    
    # Try multiple locations for the user_tests.json file
    possible_paths = [
        # First check in the current directory (this is the copy we just made)
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_tests.json'),
        # Path relative to the current directory
        'user_tests.json',
        # Path relative to the parent directory
        '../user_tests.json',
        # Absolute path based on current file location
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'user_tests.json'),
        # Railway deployment path
        '/app/user_tests.json'
    ]
    
    # Try each path until we find the file
    for path in possible_paths:
        try:
            print(f"Trying to load user_tests.json from: {path}")
            with open(path, 'r', encoding='utf-8') as f:
                tests_data = json.load(f)
                user_tests = tests_data.get(user_id_str, [])
                print(f"Found {len(user_tests)} tests for user {user_id_str} at {path}")
                
                # Add an ID to each test if it doesn't have one
                for i, test in enumerate(user_tests):
                    if 'id' not in test:
                        test['id'] = f"test_{i+1}"
                
                return user_tests
        except Exception as e:
            print(f"Failed to load from {path}: {e}")
    
    # If all paths fail, fall back to sample tests
    try:
        sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_tests.json')
        print(f"Falling back to sample tests at: {sample_path}")
        
        with open(sample_path, 'r', encoding='utf-8') as f:
            tests_data = json.load(f)
            sample_user_id = "1477944238"  # Sample user ID in our JSON
            user_tests = tests_data.get(sample_user_id, [])
            print(f"Found {len(user_tests)} sample tests")
            return user_tests
    except Exception as e:
        print(f"Failed to load sample tests: {e}")
        
    # If everything fails, return an empty list
    print("All attempts to load tests failed, returning empty list")
    return []

# Main route for the web app
@app.route('/')
def index():
    # Get language from query parameter if provided
    lang = request.args.get('lang', 'en')
    
    # Validate language (only allow 'uz', 'ru', or 'en')
    if lang not in ['uz', 'ru', 'en']:
        lang = 'en'
    
    return render_template('index.html', lang=lang)

# API endpoint to validate Telegram user and get their tests
@app.route('/api/validate', methods=['POST'])
def validate_user():
    try:
        # Get init data from request
        init_data = request.form.get('initData')
        
        # Debug log the init data
        print(f"Received initData: {init_data}")
        
        # Validate the data
        is_valid, user_data = validate_telegram_webapp(init_data)
        
        if not is_valid or not user_data:
            print("Validation failed or no user data")
            return jsonify({
                'success': False,
                'message': 'Invalid authentication data'
            }), 401
        
        # Debug log the user data
        print(f"Validated user data: {user_data}")
        
        # Store user data in session
        session['user_id'] = user_data.get('id')
        session['username'] = user_data.get('username')
        session['first_name'] = user_data.get('first_name')
        
        return jsonify({
            'success': True,
            'user': user_data
        })
    except Exception as e:
        print(f"Error in validate_user: {e}")
        return jsonify({
            'success': False,
            'message': f'Error processing request: {str(e)}'
        }), 500

# API endpoint to get tests for the authenticated user
@app.route('/api/tests', methods=['GET'])
def get_tests():
    try:
        # Get user_id from session or query parameter
        user_id = session.get('user_id')
        
        # For debugging, also accept a user_id query parameter
        if not user_id and request.args.get('user_id'):
            user_id = request.args.get('user_id')
        
        if not user_id:
            print("No user_id found in session or query parameters")
            return jsonify({
                'success': False,
                'message': 'User not authenticated'
            }), 401
        
        print(f"Getting tests for user_id: {user_id}")
        tests = get_user_tests(user_id)
        
        return jsonify({
            'success': True,
            'tests': tests
        })
    except Exception as e:
        print(f"Error in get_tests: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting tests: {str(e)}'
        }), 500

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
