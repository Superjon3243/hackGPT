document.addEventListener('DOMContentLoaded', async () => {
    const API_URL = 'http://127.0.0.1:5001/api';
    const errorMessage = document.getElementById('error-message');

    // --- Helper to get token from localStorage ---
    // Note: In a real app, token might be stored more securely (e.g., httpOnly cookie)
    // For this project, we assume the token is still available from the previous page's session.
    // A robust solution would involve passing the token or using a shared session.
    // For simplicity, we'll assume the user is still logged in and token is accessible.
    // This part of the logic is simplified for this example.
    const token = localStorage.getItem('jwt_token'); // This assumes we save the token upon login.

    // --- Get Test ID from URL ---
    const pathParts = window.location.pathname.split('/');
    const fullTestId = pathParts[pathParts.length - 1];

    if (!fullTestId) {
        showError("Could not find Test ID in the URL.");
        return;
    }

    if (!token) {
        showError("Authentication token not found. Please log in again.");
        // Redirect to login page might be appropriate here
        // window.location.href = '/';
        return;
    }

    // --- Fetch and Display Results ---
    try {
        const response = await fetch(`${API_URL}/full-test/results/${fullTestId}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.msg || 'Failed to fetch results.');
        }

        populateResults(data);

    } catch (error) {
        showError(error.message);
    }

    function populateResults(data) {
        document.getElementById('dapar-score').textContent = data.dapar_score || 'N/A';
        document.getElementById('test-status').textContent = data.status;

        const tableBody = document.querySelector('#results-table tbody');
        tableBody.innerHTML = ''; // Clear any loading spinners or placeholders

        if (data.results_by_chapter && data.results_by_chapter.length > 0) {
            data.results_by_chapter.forEach(chapter => {
                const row = tableBody.insertRow();
                row.innerHTML = `
                    <td>${chapter.chapter}</td>
                    <td>${chapter.score}</td>
                    <td>${chapter.average_difficulty}</td>
                    <td>${chapter.success_percentage}%</td>
                    <td>${chapter.average_time_per_question}s</td>
                `;
            });
        } else {
            const row = tableBody.insertRow();
            const cell = row.insertCell();
            cell.colSpan = 5;
            cell.textContent = 'No chapter data available.';
        }
    }

    function showError(message) {
        errorMessage.textContent = `Error: ${message}`;
        errorMessage.classList.remove('hidden');
    }
});

// We need to modify the login logic in app.js to save the token to localStorage.
// This is a missing piece that this results.js script depends on.
// Example for app.js loginBtn event listener:
// ...
// token = data.access_token;
// localStorage.setItem('jwt_token', token); // Add this line
// ...
