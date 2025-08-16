document.addEventListener('DOMContentLoaded', () => {
    const API_URL = 'http://127.0.0.1:5001/api';
    let token = null;
    let currentTestId = null; // ID of the current chapter test
    let fullTestId = null;    // ID of the entire test session
    let timerInterval = null;
    let questionStartTime = null;

    // --- Element Selectors ---
    const authContainer = document.getElementById('auth-container');
    const loginBtn = document.getElementById('login-btn');
    const registerBtn = document.getElementById('register-btn');
    const authMessage = document.getElementById('auth-message');
    const testContainer = document.getElementById('test-container');
    const startBtn = document.getElementById('start-full-test-btn');
    const testArea = document.getElementById('test-area');
    const chapterTitle = document.getElementById('chapter-title');
    const questionText = document.getElementById('question-text');
    const optionsContainer = document.getElementById('options-container');
    const submitAnswerBtn = document.getElementById('submit-answer-btn');
    const feedback = document.getElementById('feedback');
    const timerDisplay = document.querySelector('#timer span');

    // --- Authentication ---
    registerBtn.addEventListener('click', async () => {
        const username = document.getElementById('register-username').value;
        const password = document.getElementById('register-password').value;
        try {
            const response = await fetch(`${API_URL}/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            });
            const data = await response.json();
            authMessage.textContent = data.msg;
        } catch (error) {
            authMessage.textContent = 'Error registering.';
        }
    });

    loginBtn.addEventListener('click', async () => {
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;
        try {
            const response = await fetch(`${API_URL}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            });
            if (!response.ok) {
                throw new Error('Login failed');
            }
            const data = await response.json();
            token = data.access_token;
            localStorage.setItem('jwt_token', token); // Store token for results page
            authMessage.textContent = 'Login successful!';
            authContainer.classList.add('hidden');
            testContainer.classList.remove('hidden');
        } catch (error) {
            authMessage.textContent = 'Error logging in.';
        }
    });

    // --- Test Logic ---
    startBtn.addEventListener('click', async () => {
        try {
            const response = await fetch(`${API_URL}/full-test/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
            });
            const data = await response.json();
            if (response.ok) {
                fullTestId = data.full_test_id;
                currentTestId = data.test_id;
                updateChapter(data.chapter, data.question);
                document.getElementById('start-test-container').classList.add('hidden');
                testArea.classList.remove('hidden');
            } else {
                feedback.textContent = data.msg;
            }
        } catch (error) {
            feedback.textContent = 'Error starting test.';
        }
    });

    submitAnswerBtn.addEventListener('click', async () => {
        const selectedOption = document.querySelector('input[name="option"]:checked');
        if (!selectedOption) {
            feedback.textContent = 'Please select an answer.';
            return;
        }

        const questionId = selectedOption.dataset.questionId;
        const userAnswer = selectedOption.value;
        const timeTaken = Math.round((Date.now() - questionStartTime) / 1000);

        try {
            const response = await fetch(`${API_URL}/test/submit-answer`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({
                    test_id: currentTestId,
                    question_id: parseInt(questionId),
                    user_answer: userAnswer,
                    time_taken: timeTaken,
                }),
            });
            const data = await response.json();
            if (response.ok) {
                feedback.textContent = `Your last answer was ${data.result}. ${data.msg || ''}`;

                if (data.next_question) {
                    // This can be a new question in the same chapter or the first in the next
                    if (data.chapter) {
                        // We've transitioned to a new chapter
                        currentTestId = data.test_id;
                        updateChapter(data.chapter, data.next_question);
                    } else {
                        // Just the next question in the same chapter
                        displayQuestion(data.next_question);
                    }
                } else {
                    // Test is fully complete
                    endTest(data.msg);
                }
            } else {
                endTest(data.msg);
            }
        } catch (error) {
            feedback.textContent = 'Error submitting answer.';
        }
    });

    function updateChapter(chapter, firstQuestion) {
        chapterTitle.textContent = `Chapter: ${chapter.charAt(0).toUpperCase() + chapter.slice(1)}`;
        startTimer(15 * 60); // Reset timer for each new chapter
        displayQuestion(firstQuestion);
    }

    function displayQuestion(question) {
        questionStartTime = Date.now();

        const questionContainer = document.getElementById('question-container');
        // Clear previous question content (text, image, options)
        questionContainer.innerHTML = '';

        // Add image if it exists
        if (question.image_url) {
            const img = document.createElement('img');
            img.src = question.image_url;
            img.alt = 'Question visual content';
            img.className = 'question-image';
            questionContainer.appendChild(img);
        }

        // Add question text
        const textP = document.createElement('p');
        textP.id = 'question-text';
        textP.textContent = question.text;
        questionContainer.appendChild(textP);

        // Add options
        const optionsDiv = document.createElement('div');
        optionsDiv.id = 'options-container';
        question.options.forEach(option => {
            const div = document.createElement('div');
            div.className = 'option';
            const radio = document.createElement('input');
            radio.type = 'radio';
            radio.name = 'option';
            radio.value = option;
            radio.id = `option-${option}`;
            radio.dataset.questionId = question.id;
            const label = document.createElement('label');
            label.htmlFor = `option-${option}`;
            label.textContent = option;
            div.appendChild(radio);
            div.appendChild(label);
            optionsDiv.appendChild(div);
        });
        questionContainer.appendChild(optionsDiv);
    }

    function startTimer(duration) {
        if (timerInterval) clearInterval(timerInterval); // Clear any existing timer
        let timer = duration;
        timerInterval = setInterval(() => {
            const minutes = Math.floor(timer / 60);
            const seconds = timer % 60;
            timerDisplay.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            if (--timer < 0) {
                endTest('Time is up!');
            }
        }, 1000);
    }

    function endTest(message) {
        clearInterval(timerInterval);
        // Redirect to the results page
        if (fullTestId) {
            window.location.href = `/results/${fullTestId}`;
        } else {
            testArea.innerHTML = `<h2>Test Over</h2><p>${message}</p><p>Could not retrieve final results ID.</p>`;
        }
    }
});
