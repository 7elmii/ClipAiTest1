document.getElementById('clip-button').addEventListener('click', async () => {
    const url = document.getElementById('youtube-url').value;
    const resultArea = document.getElementById('result-area');
    const loader = document.getElementById('loader');
    const statusText = document.getElementById('status-text');

    if (!url) {
        alert('Please enter a YouTube URL.');
        return;
    }

    resultArea.innerHTML = '';
    loader.style.display = 'flex';
    statusText.textContent = 'Processing...';

    try {
        const response = await fetch('http://127.0.0.1:5000/clip', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url })
        });

        const data = await response.json();

        if (response.ok) {
            const video = document.createElement('video');
            video.src = data.video_url;
            video.controls = true;
            resultArea.appendChild(video);
        } else {
            resultArea.innerHTML = `<div class="error-message">Error: ${data.error}</div>`;
        }
    } catch (error) {
        resultArea.innerHTML = `<div class="error-message">An unexpected error occurred. Please check the console.</div>`;
    }

    loader.style.display = 'none';
});
