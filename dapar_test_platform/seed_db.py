from app import app, db, Question, User
import json
import random

def add_dummy_data():
    """
    Clears existing data and populates the database with dummy questions and a test user.
    """
    # Use app_context to interact with the application's database
    with app.app_context():
        # Clear existing data
        db.drop_all()
        db.create_all()

        # Add dummy questions
        chapters = ['verbal', 'quantitative', 'shapes', 'instructions']
        questions_to_add = []
        for chapter in chapters:
            for difficulty in range(1, 11):
                for i in range(20):  # 20 questions per difficulty level
                    options = [f"Option {j}" for j in range(1, 5)]

                    image_url = None
                    if chapter == 'shapes':
                        # Add a placeholder image for shape questions
                        image_url = f"https://via.placeholder.com/250.png?text=Shape+{i+1}"

                    question = Question(
                        chapter=chapter,
                        difficulty=difficulty,
                        text=f"This is {chapter} question #{i+1} (difficulty {difficulty}). What is the answer?",
                        options=json.dumps(options),
                        correct_answer=random.choice(options),
                        image_url=image_url
                    )
                    questions_to_add.append(question)

        db.session.bulk_save_objects(questions_to_add)

        # Add a default user for testing
        if not User.query.filter_by(username='testuser').first():
            test_user = User(username='testuser')
            test_user.set_password('password')
            db.session.add(test_user)

        db.session.commit()
        print("Database has been seeded with dummy data.")

if __name__ == '__main__':
    add_dummy_data()
