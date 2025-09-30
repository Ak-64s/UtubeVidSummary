# YouTube Video Summarizer

AI-powered YouTube video summarization tool using Google's Gemini API.

## Features

- 🎥 Summarize YouTube videos instantly
- 🤖 Powered by Google Gemini AI
- ⏱️ Support for video segments (timestamp-based)
- 💾 Smart caching for faster responses
- 🌐 Modern, responsive UI
- 🔒 Secure with CSP headers

## Tech Stack

- **Backend**: Flask (Python 3.11)
- **AI**: Google Gemini API
- **Caching**: Redis / In-memory
- **Frontend**: Vanilla JS with Markdown rendering
- **Deployment**: Vercel-ready

## Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd ProjectBeta
   ```

2. **Install dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   Create a `.env` file:
   ```env
   FLASK_SECRET_KEY=your-secret-key-here
   GEMINI_API_KEY=your-gemini-api-key
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open browser**
   Navigate to `http://localhost:5000`

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

### Quick Deploy to Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/yourusername/your-repo)

## Configuration

All configuration is done via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_SECRET_KEY` | Secret key for Flask sessions | **Required** |
| `GEMINI_API_KEY` | Google Gemini API key | **Required** |
| `FLASK_DEBUG` | Enable debug mode | `true` |
| `USE_YOUTUBE_TRANSCRIPT_API` | Use YouTube Transcript API | `true` |
| `TRANSCRIPT_LANGUAGES` | Preferred transcript languages | `hi,en,en-US,en-GB` |
| `USE_REDIS` | Enable Redis caching | `false` |
| `REDIS_URL` | Redis connection URL | - |

## API Endpoints

- `GET /` - Home page
- `POST /submit_task` - Submit video for processing
- `GET /task_status/<task_id>` - Check processing status
- `GET /results` - View results
- `GET /health` - Health check
- `GET /system_info` - System information

## Project Structure

```
ProjectBeta/
├── controllers/      # Business logic
├── models/          # Data models
├── routes/          # API & web routes
├── services/        # Background services
├── utils/           # Helper utilities
├── middleware/      # HTTP middleware
├── static/          # CSS & JS
├── templates/       # HTML templates
├── app.py          # Application entry point
├── config.py       # Configuration
└── constants.py    # Application constants
```

## License

MIT

## Support

For issues and questions, please open an issue on GitHub.
