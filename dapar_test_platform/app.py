from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, JWTManager
from flask_cors import CORS
import os
import json
import random
from datetime import datetime

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# --- Constants ---
CHAPTER_ORDER = ['verbal', 'shapes', 'quantitative', 'instructions']
QUESTIONS_PER_CHAPTER = 15

# --- Configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'a-different-super-secret-for-production' # Change this!

db = SQLAlchemy(app)
jwt = JWTManager(app)

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class FullTest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(50), default=CHAPTER_ORDER[0], nullable=False) # e.g. verbal, quantitative, completed
    dapar_score = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('full_tests', lazy=True))

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chapter = db.Column(db.String(50), nullable=False)
    difficulty = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text, nullable=False)
    correct_answer = db.Column(db.String(255), nullable=False)
    image_url = db.Column(db.String(255), nullable=True) # New field for image-based questions
    def to_dict(self):
        return {
            'id': self.id,
            'chapter': self.chapter,
            'difficulty': self.difficulty,
            'text': self.text,
            'options': json.loads(self.options),
            'image_url': self.image_url
        }

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    full_test_id = db.Column(db.Integer, db.ForeignKey('full_test.id'), nullable=False)
    chapter = db.Column(db.String(50), nullable=False)
    final_score = db.Column(db.Float, nullable=True)
    current_difficulty = db.Column(db.Integer, default=5, nullable=False)
    user = db.relationship('User', backref=db.backref('tests', lazy=True))
    full_test = db.relationship('FullTest', backref=db.backref('tests', lazy=True, cascade="all, delete-orphan"))

class TestAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    user_answer = db.Column(db.String(255), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    time_taken = db.Column(db.Integer, nullable=True) # in seconds
    test = db.relationship('Test', backref=db.backref('answers', lazy=True, cascade="all, delete-orphan"))
    question = db.relationship('Question')

# --- Webpage & API Endpoints ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username, password = data.get('username'), data.get('password')
    if not username or not password: return jsonify({"msg": "Username and password required"}), 400
    if User.query.filter_by(username=username).first(): return jsonify({"msg": "Username already exists"}), 400
    new_user = User(username=username)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"msg": "User created successfully"}), 201

import sys

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username, password = data.get('username'), data.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            access_token = create_access_token(identity=str(user.id))
            return jsonify(access_token=access_token)

        return jsonify({"msg": "Bad username or password"}), 401
    except Exception as e:
        # It's good practice to log the error
        print(f"An error occurred in login: {e}", file=sys.stderr)
        return jsonify({"msg": "Internal server error"}), 500

# --- Scoring Logic ---
def _calculate_chapter_score(chapter_test):
    """Calculates score for a chapter based on avg difficulty and success rate."""
    if not chapter_test.answers:
        return 0

    answered_questions = [a.question for a in chapter_test.answers]
    avg_difficulty = sum(q.difficulty for q in answered_questions) / len(answered_questions)

    correct_answers = sum(1 for a in chapter_test.answers if a.is_correct)
    success_rate = correct_answers / len(chapter_test.answers)

    # Formula: 50% from difficulty (scaled 1-10 to 0-100) and 50% from success rate (0-1 to 0-100)
    score = (avg_difficulty * 10 * 0.5) + (success_rate * 100 * 0.5)
    return round(score, 2)

def _calculate_dapar_score(full_test):
    """Calculates the final Dapar score (10-90) from all chapter scores."""
    chapter_scores = [test.final_score for test in full_test.tests if test.final_score is not None]
    if not chapter_scores:
        return None

    # Average the chapter scores (which are on a ~0-100 scale)
    average_score = sum(chapter_scores) / len(chapter_scores)

    # Scale the 0-100 score to the 10-90 Dapar range
    # A score of 0 maps to 10, a score of 100 maps to 90.
    scaled_score = 10 + (average_score / 100) * 80
    return round(scaled_score, 2)

# --- Test Logic ---
def get_next_question_for_test(test):
    answered_ids = [a.question_id for a in test.answers]
    q = Question.query.filter(Question.chapter == test.chapter, Question.difficulty == test.current_difficulty, Question.id.notin_(answered_ids)).first()
    if not q and test.current_difficulty < 10: q = Question.query.filter(Question.chapter == test.chapter, Question.difficulty == test.current_difficulty + 1, Question.id.notin_(answered_ids)).first()
    if not q and test.current_difficulty > 1: q = Question.query.filter(Question.chapter == test.chapter, Question.difficulty == test.current_difficulty - 1, Question.id.notin_(answered_ids)).first()
    return q

@app.route('/api/test/start', methods=['POST'])
@jwt_required()
def start_test():
    # This endpoint is now deprecated in favor of the full_test flow
    user_id = get_jwt_identity()
    chapter = request.get_json().get('chapter')
    if not chapter: return jsonify({"msg": "Chapter is required"}), 400

    # Create a dummy FullTest for this single chapter test
    full_test = FullTest(user_id=user_id, status=chapter)
    db.session.add(full_test)
    db.session.commit()

    new_test = Test(user_id=user_id, full_test_id=full_test.id, chapter=chapter, current_difficulty=5)
    db.session.add(new_test)
    db.session.commit()

    question = get_next_question_for_test(new_test)
    if not question: return jsonify({"msg": f"No questions for chapter '{chapter}'"}), 404
    return jsonify({"test_id": new_test.id, "question": question.to_dict()})

@app.route('/api/full-test/start', methods=['POST'])
@jwt_required()
def start_full_test():
    user_id = get_jwt_identity()
    first_chapter = CHAPTER_ORDER[0]

    # Create the main test object that tracks the entire process
    full_test = FullTest(user_id=user_id, status=first_chapter)
    db.session.add(full_test)
    db.session.commit()

    # Create the first chapter's test
    chapter_test = Test(user_id=user_id, full_test_id=full_test.id, chapter=first_chapter, current_difficulty=5)
    db.session.add(chapter_test)
    db.session.commit()

    question = get_next_question_for_test(chapter_test)
    if not question: return jsonify({"msg": f"No questions available to start test"}), 404

    return jsonify({
        "full_test_id": full_test.id,
        "test_id": chapter_test.id, # This is the ID for the current chapter's test
        "question": question.to_dict(),
        "chapter": first_chapter
    })

@app.route('/api/test/submit-answer', methods=['POST'])
@jwt_required()
def submit_answer():
    user_id = get_jwt_identity()
    data = request.get_json()
    test_id = data.get('test_id')

    chapter_test = Test.query.filter_by(id=test_id, user_id=user_id).first()
    if not chapter_test: return jsonify({"msg": "Test not found"}), 404

    full_test = chapter_test.full_test
    if not full_test: return jsonify({"msg": "Full test container not found"}), 404

    if len(chapter_test.answers) >= QUESTIONS_PER_CHAPTER:
        return jsonify({"msg": "This chapter is already completed"}), 400

    question = Question.query.get(data.get('question_id'))
    if not question: return jsonify({"msg": "Question not found"}), 404

    # Save the answer
    is_correct = (str(data.get('user_answer')) == str(question.correct_answer))
    db.session.add(TestAnswer(test_id=chapter_test.id, question_id=question.id, user_answer=str(data.get('user_answer')), is_correct=is_correct, time_taken=data.get('time_taken')))

    # Update difficulty for the current chapter
    chapter_test.current_difficulty = min(10, chapter_test.current_difficulty + 1) if is_correct else max(1, chapter_test.current_difficulty - 1)
    db.session.commit()

    # Check if the chapter is complete
    if len(chapter_test.answers) >= QUESTIONS_PER_CHAPTER:
        # --- Chapter is complete, transition to next ---
        current_chapter_index = CHAPTER_ORDER.index(chapter_test.chapter)

        # Calculate and save chapter score
        chapter_test.final_score = _calculate_chapter_score(chapter_test)

        if current_chapter_index + 1 < len(CHAPTER_ORDER):
            # --- Move to the next chapter ---
            next_chapter_name = CHAPTER_ORDER[current_chapter_index + 1]
            full_test.status = next_chapter_name

            # Create the new chapter test
            next_chapter_test = Test(user_id=user_id, full_test_id=full_test.id, chapter=next_chapter_name, current_difficulty=5)
            db.session.add(next_chapter_test)
            db.session.commit()

            next_question = get_next_question_for_test(next_chapter_test)
            if not next_question: return jsonify({"msg": "Test completed", "reason": f"No questions in new chapter '{next_chapter_name}'", "full_test_id": full_test.id})

            return jsonify({
                "result": "correct" if is_correct else "incorrect",
                "msg": f"Chapter {chapter_test.chapter} completed. Starting {next_chapter_name}.",
                "next_question": next_question.to_dict(),
                "test_id": next_chapter_test.id, # Pass the new test_id for the next chapter
                "chapter": next_chapter_name
            })
        else:
            # --- This was the last chapter, the full test is complete ---
            full_test.status = 'completed'
            full_test.dapar_score = _calculate_dapar_score(full_test)
            db.session.commit()
            return jsonify({"msg": "Test completed", "full_test_id": full_test.id})
    else:
        # --- Chapter is not complete, get next question ---
        next_question = get_next_question_for_test(chapter_test)
        if not next_question:
            # This can happen if we run out of questions of a certain difficulty
            full_test.status = 'completed_incomplete' # Mark as abnormally completed
            db.session.commit()
            return jsonify({"msg": "Test completed", "reason": "No more questions available", "full_test_id": full_test.id})

        return jsonify({"result": "correct" if is_correct else "incorrect", "next_question": next_question.to_dict()})

@app.route('/api/full-test/results/<int:full_test_id>', methods=['GET'])
@jwt_required()
def get_full_test_results(full_test_id):
    user_id = get_jwt_identity()
    full_test = FullTest.query.get(full_test_id)

    if not full_test:
        return jsonify({"msg": "Test results not found"}), 404

    if str(full_test.user_id) != user_id:
        return jsonify({"msg": "Unauthorized"}), 403

    if full_test.status != 'completed':
        return jsonify({"msg": "Test is not yet completed"}), 400

    chapter_results = []
    for test in full_test.tests:
        if not test.answers:
            continue

        total_time = sum(a.time_taken for a in test.answers if a.time_taken is not None)
        avg_time = total_time / len(test.answers) if len(test.answers) > 0 else 0

        correct_answers = sum(1 for a in test.answers if a.is_correct)
        success_percentage = (correct_answers / len(test.answers)) * 100 if len(test.answers) > 0 else 0

        answered_questions = [a.question for a in test.answers]
        avg_difficulty = sum(q.difficulty for q in answered_questions) / len(answered_questions)

        chapter_results.append({
            "chapter": test.chapter,
            "score": test.final_score,
            "average_difficulty": round(avg_difficulty, 2),
            "success_percentage": round(success_percentage, 2),
            "average_time_per_question": round(avg_time, 2)
        })

    return jsonify({
        "full_test_id": full_test.id,
        "dapar_score": full_test.dapar_score,
        "status": full_test.status,
        "completed_at": full_test.created_at.isoformat(), # This should be an updated_at field ideally
        "results_by_chapter": chapter_results
    })

if __name__ == '__main__':
    app.run(debug=True, port=5001)

# --- Frontend Routes ---
@app.route('/results/<int:full_test_id>')
def results_page(full_test_id):
    # This route simply serves the HTML page.
    # The actual data is fetched by results.js via the API.
    return render_template('results.html')
