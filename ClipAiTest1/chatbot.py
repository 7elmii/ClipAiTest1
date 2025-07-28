from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pytube import YouTube
import whisper
import ffmpeg
import os
import traceback
import sys
from openai import OpenAI # Import OpenAI library

# --- IMPORTANT: OpenAI API Key Configuration ---
# To use this script, you need an OpenAI API key.
# 1. Get your key from https://platform.openai.com/account/api-keys
# 2. Set it as an environment variable named OPENAI_API_KEY.
#    - On Windows: setx OPENAI_API_KEY "your-key-here"
#    - On macOS/Linux: export OPENAI_API_KEY="your-key-here"
#    You will need to restart your command prompt after setting the variable.

try:
    client = OpenAI()
except Exception as e:
    print("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.", file=sys.stderr)
    sys.exit(1)

app = Flask(__name__, static_folder='.')
CORS(app)

# --- Helper Function (OpenAI Analysis) ---

def get_best_moment_with_openai(transcription):
    """Uses OpenAI to find the most impactful segment of a video."""
    print("Analyzing transcript with OpenAI...")
    
    # Combine the transcript segments into a single block of text
    full_transcript_text = " ".join([seg['text'] for seg in transcription['segments']])

    # Create the prompt for the AI
    prompt = f"""The following is a transcript of a YouTube video:

---
{full_transcript_text}
---

Analyze the transcript and identify the single most exciting, climactic, or emotionally impactful 30-60 second moment. Your response MUST be only the start and end timestamps (in seconds) of that moment, formatted as 'start_time,end_time'. For example: '123.45,170.21'. Do not include any other text or explanation."""

    # Call the OpenAI API
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an expert video editor."},
            {"role": "user", "content": prompt}
        ]
    )

    # Parse the response
    content = response.choices[0].message.content
    start_time, end_time = map(float, content.strip().split(','))
    return start_time, end_time

# --- Core Application ---

@app.route('/clip', methods=['POST'])
def clip_video():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        print("--- New Request Received ---")
        print(f"URL: {url}")
        sys.stdout.flush()

        # 1. Download Audio
        print("Step 1/5: Downloading audio...")
        yt = YouTube(url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        audio_path = audio_stream.download(filename_prefix="audio_")
        print(f"Audio downloaded to: {audio_path}")
        sys.stdout.flush()

        # 2. Transcribe Audio
        print("Step 2/5: Transcribing audio with Whisper...")
        model = whisper.load_model("base")
        transcription = model.transcribe(audio_path)
        print("Transcription complete.")
        sys.stdout.flush()

        # 3. Find Best Moment with OpenAI
        print("Step 3/5: Finding best moment with OpenAI...")
        start_time, end_time = get_best_moment_with_openai(transcription)
        print(f"Best segment identified by AI: {start_time}s - {end_time}s")
        sys.stdout.flush()

        # 4. Download Video and Create Subtitles
        print("Step 4/5: Downloading video and creating subtitles...")
        video_stream = yt.streams.get_highest_resolution()
        video_path = video_stream.download(filename_prefix="video_")
        
        subtitle_path = os.path.abspath(f"subs_{yt.video_id}.srt")
        with open(subtitle_path, "w", encoding='utf-8') as f:
            for i, segment in enumerate(transcription['segments']):
                start = segment['start']
                end = segment['end']
                text = segment['text']
                f.write(f"{i+1}\n{start} --> {end}\n{text}\n\n")
        print(f"Video and subtitles ready.")
        sys.stdout.flush()

        # 5. Clip Video with FFmpeg
        print("Step 5/5: Clipping video and burning subtitles...")
        output_path = f"clip_{yt.video_id}.mp4"
        escaped_subtitle_path = subtitle_path.replace('\\', '/').replace(':', '\\:')

        (   ffmpeg
            .input(video_path, ss=start_time)
            .output(output_path, vf=f"subtitles={escaped_subtitle_path}", to=end_time)
            .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
        )
        print("Video clipping complete.")
        sys.stdout.flush()

        # Cleanup
        os.remove(audio_path)
        os.remove(video_path)
        os.remove(subtitle_path)

        return jsonify({'video_url': f'/{output_path}'})

    except ffmpeg.Error as e:
        print("FFMPEG Error:", file=sys.stderr)
        print(e.stderr.decode(), file=sys.stderr)
        sys.stderr.flush()
        return jsonify({'error': 'FFmpeg failed. Is it installed and in your PATH?'}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.stderr.flush()
        return jsonify({'error': 'An internal server error occurred. Check the console for details.'}), 500

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    print("--- Starting Flask Server ---")
    print("Open http://127.0.0.1:5000/index.html in your browser.")
    app.run(debug=True, use_reloader=False)