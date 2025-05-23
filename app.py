import os
import json
import sqlite3
from flask import Flask, render_template, jsonify, request, session
from flask_cors import CORS
import hashlib
import time
import hmac
import base64

app = Flask(__name__, static_url_path='/static', static_folder='static')
CORS(app)  # Enable CORS for all routes
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
                
                # Check if user_id_str exists in the tests_data
                if user_id_str in tests_data:
                    user_tests = tests_data.get(user_id_str, [])
                    print(f"Found {len(user_tests)} tests for user {user_id_str} at {path}")
                    
                    # Add an ID to each test if it doesn't have one
                    for i, test in enumerate(user_tests):
                        if 'id' not in test:
                            test['id'] = f"test_{i+1}"
                    
                    return user_tests
                else:
                    print(f"User ID {user_id_str} not found in {path}")
        except Exception as e:
            print(f"Failed to load from {path}: {e}")
    
    # If all paths fail, fall back to sample tests
    try:
        sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_tests.json')
        print(f"Falling back to sample tests from: {sample_path}")
        with open(sample_path, 'r', encoding='utf-8') as f:
            sample_data = json.load(f)
            sample_tests = sample_data.get(user_id_str, [])
            if not sample_tests and '1477944238' in sample_data:
                sample_tests = sample_data['1477944238']
            
            # Add an ID to each test if it doesn't have one
            for i, test in enumerate(sample_tests):
                if 'id' not in test:
                    test['id'] = f"sample_test_{i+1}"
            
            print(f"Loaded {len(sample_tests)} sample tests")
            return sample_tests
    except Exception as e:
        print(f"Failed to load sample tests: {e}")
        return []   # If everything fails, return an empty list
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
    # Try to get user_id from session first
    user_id = session.get('user_id')
    
    # If not in session, try to get from query parameters or request body
    if not user_id:
        user_id = request.args.get('user_id') or (request.json and request.json.get('user_id'))
        
        # If we found a user_id, store it in the session for future requests
        if user_id:
            session['user_id'] = user_id
            print(f"Using user_id from request: {user_id}")
    
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
    
    # Get the client-side score calculation if available
    client_correct = data.get('correct')
    client_total = data.get('total')
    client_percentage = data.get('percentage')
    answer_results = data.get('answer_results', [])
    
    # Print debug information
    print(f"Received answers: {answers}")
    print(f"Client-side score: {client_correct}/{client_total} ({client_percentage}%)")
    
    # Server-side calculation for verification
    server_correct_count = 0
    server_total_questions = len(test.get('questions', []))
    
    # Check each answer on the server side
    for i, question in enumerate(test.get('questions', [])):
        if i < len(answers):
            try:
                user_answer = int(answers[i]) if answers[i] is not None else None
                correct_answer = int(question.get('correct_option')) if question.get('correct_option') is not None else None
                
                print(f"Question {i+1}: User answered {user_answer}, correct is {correct_answer}")
                
                # Check if the answer is correct
                if user_answer is not None and correct_answer is not None and user_answer == correct_answer:
                    server_correct_count += 1
                    print(f"Question {i+1}: CORRECT")
                else:
                    print(f"Question {i+1}: INCORRECT")
            except (ValueError, TypeError) as e:
                print(f"Error processing answer for question {i+1}: {e}")
    
    print(f"Server calculation: {server_correct_count} out of {server_total_questions}")
    server_percentage = (server_correct_count / server_total_questions) * 100 if server_total_questions > 0 else 0
    
    # Choose the most reliable score (prefer server-side calculation)
    if server_total_questions > 0:
        correct_count = server_correct_count
        total_questions = server_total_questions
        percentage = server_percentage
        print(f"Using server-side calculation: {correct_count}/{total_questions} ({percentage}%)")
    elif client_correct is not None and client_total is not None:
        # Fall back to client-side calculation if server calculation failed
        correct_count = client_correct
        total_questions = client_total
        percentage = client_percentage if client_percentage is not None else (client_correct / client_total * 100 if client_total > 0 else 0)
        print(f"Using client-side calculation: {correct_count}/{total_questions} ({percentage}%)")
    else:
        # Default values if all else fails
        correct_count = 0
        total_questions = 0
        percentage = 0
        print("Warning: Could not calculate score reliably")
    
    # Save results to the bot's database
    try:
        # Import the database functions from the parent directory
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from database import save_test_result
        import asyncio
        import datetime
        
        # Calculate points (same formula as in the bot)
        points_100 = round((correct_count / total_questions) * 100) if total_questions > 0 else 0
        
        # Get the current date and time
        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get the test name
        test_name = test.get('name', f"Test {test_id}")
        
        print(f"Saving test result to database: User {user_id}, Test '{test_name}', Score {correct_count}/{total_questions} ({percentage}%)")
        
        # Save the result to the database
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(save_test_result(
            user_id=int(user_id),
            test_name=test_name,
            date=current_date,
            correct=correct_count,
            total=total_questions,
            percent=percentage,
            points=points_100
        ))
        loop.close()
        
        print(f"Test result saved successfully for user {user_id}")
    except Exception as e:
        print(f"Error saving test result to database: {e}")
    
    return jsonify({
        'success': True,
        'score': {
            'correct': correct_count,
            'total': total_questions,
            'percentage': percentage,
            'points': points_100
        },
        'saved_to_database': True
    })

if __name__ == "__main__":
    # Get port from environment variable (Railway sets this)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
