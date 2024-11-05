// Fetch status on load
fetch('/api/status')
    .then(response => response.json())
    .then(data => {
        const statusDiv = document.getElementById('status');
        statusDiv.innerHTML = JSON.stringify(data, null, 2); // For simple display
    })
    .catch(error => console.error('Error fetching status:', error));
