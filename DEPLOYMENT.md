# Vercel Deployment Guide

## Prerequisites

- A Vercel account ([sign up here](https://vercel.com))
- Gemini API key from [Google AI Studio](https://ai.google.dev/gemini-api)

## Quick Deploy

### Option 1: Deploy via Vercel CLI

1. **Install Vercel CLI**
   ```bash
   npm i -g vercel
   ```

2. **Login to Vercel**
   ```bash
   vercel login
   ```

3. **Deploy**
   ```bash
   vercel
   ```

### Option 2: Deploy via Vercel Dashboard

1. **Push to GitHub**
   - Create a new repository on GitHub
   - Push your code:
     ```bash
     git init
     git add .
     git commit -m "Initial commit"
     git remote add origin https://github.com/yourusername/your-repo.git
     git push -u origin main
     ```

2. **Import to Vercel**
   - Go to [Vercel Dashboard](https://vercel.com/dashboard)
   - Click "Add New Project"
   - Import your GitHub repository
   - Vercel will auto-detect the Flask app

3. **Configure Environment Variables**
   Add these in Vercel Dashboard → Settings → Environment Variables:

   **Required:**
   - `FLASK_SECRET_KEY` - A secure random string (generate one with `python -c "import secrets; print(secrets.token_hex(32))"`)
   - `GEMINI_API_KEY` - Your Gemini API key

   **Optional:**
   - `GOOGLE_API_KEY` - Alternative API key name
   - `API_KEY` - Alternative API key name
   - `LOGGING_LEVEL` - Default: `INFO`
   - `USE_YOUTUBE_TRANSCRIPT_API` - Default: `true`
   - `TRANSCRIPT_LANGUAGES` - Default: `hi,en,en-US,en-GB`
   - `REDIS_URL` - If using Redis (optional)
   - `USE_REDIS` - Default: `false`
   - `ENABLE_HSTS` - Default: `false` (set to `true` for HTTPS)

4. **Deploy**
   - Click "Deploy"
   - Wait for deployment to complete
   - Your app will be live at `your-project.vercel.app`

## Important Notes

### Redis Configuration
- **Local Development**: Uses in-memory caching by default
- **Production**: For better performance, use a Redis instance
  - Get free Redis at [Upstash](https://upstash.com/) or [Redis Cloud](https://redis.com/try-free/)
  - Set `USE_REDIS=true` and provide `REDIS_URL`

### Serverless Limitations
- Each function invocation has a **10-second timeout** on free tier (60 seconds on Pro)
- Long videos may timeout - consider:
  - Using Redis for caching
  - Breaking into smaller segments
  - Upgrading to Vercel Pro

### Security
- Always set `FLASK_ENV=production` in Vercel
- Never commit `.env` files
- Use Vercel's environment variables for secrets

## Testing Deployment

After deployment, test these endpoints:

1. **Homepage**: `https://your-project.vercel.app/`
2. **Health Check**: `https://your-project.vercel.app/health`
3. **System Info**: `https://your-project.vercel.app/system_info`

## Troubleshooting

### Build Fails
- Check Python version in `runtime.txt` matches requirements
- Verify all dependencies are in `requirements.txt`
- Check Vercel build logs

### Application Errors
- Check Function logs in Vercel Dashboard
- Verify environment variables are set correctly
- Ensure `FLASK_SECRET_KEY` is set

### Timeout Issues
- Use Redis for caching to speed up responses
- Process shorter video segments
- Consider upgrading to Vercel Pro for longer timeouts

## Local Development

Run locally with:
```bash
python app.py
```

## Support

For issues:
- Check Vercel documentation: https://vercel.com/docs
- Review application logs in Vercel Dashboard
- Ensure all environment variables are configured
