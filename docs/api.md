# YouTube Video Summarizer API Documentation

## Overview
The YouTube Video Summarizer API provides endpoints for summarizing YouTube videos and playlists using AI-powered text analysis.

## Base URL
```
http://localhost:5000
```

## Authentication
Currently, the API requires no authentication. However, rate limiting is implemented to prevent abuse.

## Rate Limits
- Transcript fetching: 100 requests per hour
- Summary generation: 50 requests per hour
- Playlist processing: 20 requests per hour

## Endpoints

### 1. Submit Video/Playlist for Summarization
```http
POST /submit
```

#### Request Body
```json
{
    "link": "string",      // YouTube video or playlist URL
    "prompt": "string"     // Optional custom prompt for summarization
}
```

#### Response
```json
{
    "transcript": "string",  // Full transcript of the video(s)
    "summary": "string"      // AI-generated summary
}
```

#### Error Responses
- 400 Bad Request: Invalid URL or missing required fields
- 429 Too Many Requests: Rate limit exceeded
- 500 Internal Server Error: Server-side error

### 2. Check Progress (for Playlists)
```http
GET /progress/{task_id}
```

#### Response
```json
{
    "total": "number",           // Total number of videos
    "completed": "number",       // Number of processed videos
    "current_item": "string",    // Currently processing video
    "status": "string",          // in_progress, completed, or failed
    "start_time": "string",      // ISO timestamp
    "last_update": "string",     // ISO timestamp
    "errors": [                  // Array of errors if any
        {
            "item": "string",
            "error": "string",
            "timestamp": "string"
        }
    ]
}
```

## Error Codes
- 400: Bad Request - Invalid input
- 404: Not Found - Resource not found
- 429: Too Many Requests - Rate limit exceeded
- 500: Internal Server Error - Server-side error

## Examples

### Summarize a Single Video
```bash
curl -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    -d '{
        "link": "https://www.youtube.com/watch?v=example",
        "prompt": "Summarize this video focusing on key points"
    }'
```

### Process a Playlist
```bash
curl -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    -d '{
        "link": "https://www.youtube.com/playlist?list=example"
    }'
```

### Check Progress
```bash
curl http://localhost:5000/progress/task_123
```

## Best Practices
1. Always handle rate limits in your application
2. Use appropriate error handling
3. Cache results when possible
4. Monitor progress for playlist processing
5. Use custom prompts for better summaries

## Rate Limiting
The API implements rate limiting to ensure fair usage. When the rate limit is exceeded, the API will return a 429 status code. Implement exponential backoff in your application to handle rate limits gracefully.

## Caching
Results are cached for 1 hour by default. Use the cached results when available to reduce API calls and improve performance.

## Error Handling
Always check the response status code and handle errors appropriately. The API provides detailed error messages to help diagnose issues.

## Support
For support or to report issues, please open an issue on the project's GitHub repository. 