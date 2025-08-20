#!/usr/bin/env python3
"""
System Check Script for YouTube Video Processing App
This script checks system requirements and provides optimization suggestions.
"""

import shutil
import subprocess
import sys
import platform
import importlib.util
from pathlib import Path

def check_python_version():
    """Check if Python version is suitable."""
    version = sys.version_info
    print(f"✓ Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("⚠️  Warning: Python 3.8+ recommended for best compatibility")
        return False
    return True

def check_ffmpeg():
    """Check if FFmpeg is installed and accessible."""
    ffmpeg_path = shutil.which('ffmpeg')
    
    if ffmpeg_path:
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            version_line = result.stdout.split('\n')[0]
            print(f"✓ FFmpeg found: {version_line}")
            return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            print("⚠️  FFmpeg found but not responding correctly")
            return False
    else:
        print("❌ FFmpeg not found")
        print("📋 Installation instructions:")
        
        system = platform.system().lower()
        if system == "windows":
            print("   • Download from: https://ffmpeg.org/download.html#build-windows")
            print("   • Or install with chocolatey: choco install ffmpeg")
        elif system == "darwin":  # macOS
            print("   • Install with Homebrew: brew install ffmpeg")
        elif system == "linux":
            print("   • Ubuntu/Debian: sudo apt install ffmpeg")
            print("   • CentOS/RHEL: sudo yum install ffmpeg")
            print("   • Arch: sudo pacman -S ffmpeg")
        
        return False

def check_required_packages():
    """Check if required Python packages are installed."""
    required_packages = [
        'flask',
        'yt_dlp',
        'youtube_transcript_api',
        'google.generativeai',
        'requests',
        'redis'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        spec = importlib.util.find_spec(package.replace('.', '/'))
        if spec is None:
            missing_packages.append(package)
            print(f"❌ Missing package: {package}")
        else:
            print(f"✓ Package found: {package}")
    
    if missing_packages:
        print(f"\n📋 Install missing packages:")
        print(f"   pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_yt_dlp_version():
    """Check yt-dlp version and suggest updates if needed."""
    try:
        import yt_dlp
        version = yt_dlp.version.__version__
        print(f"✓ yt-dlp version: {version}")
        
        # Check if version is from 2024 or newer
        year = int(version.split('.')[0])
        if year < 2024:
            print("⚠️  Consider updating yt-dlp for better YouTube compatibility:")
            print("   pip install --upgrade yt-dlp")
            return False
        return True
    except ImportError:
        print("❌ yt-dlp not installed")
        return False
    except Exception as e:
        print(f"⚠️  Could not determine yt-dlp version: {e}")
        return False

def check_cookies_file():
    """Check if cookies file exists and is readable."""
    cookies_path = Path("cookies.txt")
    
    if cookies_path.exists():
        try:
            with open(cookies_path, 'r') as f:
                content = f.read()
                if "youtube.com" in content:
                    print("✓ Cookies file found and contains YouTube cookies")
                    return True
                else:
                    print("⚠️  Cookies file exists but may not contain YouTube cookies")
                    return False
        except Exception as e:
            print(f"❌ Cannot read cookies file: {e}")
            return False
    else:
        print("⚠️  Cookies file not found (cookies.txt)")
        print("📋 Consider creating a cookies file for better YouTube compatibility")
        return False

def check_environment_variables():
    """Check if required environment variables are set."""
    import os
    
    required_env_vars = [
        'FLASK_SECRET_KEY',
        ('GEMINI_API_KEY', 'GOOGLE_API_KEY', 'API_KEY', 'API_KEY1', 'API_KEY2')
    ]
    
    all_good = True
    
    # Check Flask secret key
    if os.getenv('FLASK_SECRET_KEY'):
        print("✓ FLASK_SECRET_KEY is set")
    else:
        print("❌ FLASK_SECRET_KEY not set")
        print("📋 Set with: export FLASK_SECRET_KEY='your-secret-key'")
        all_good = False
    
    # Check API keys (at least one should be set)
    api_key_vars = ['GEMINI_API_KEY', 'GOOGLE_API_KEY', 'API_KEY', 'API_KEY1', 'API_KEY2']
    api_keys_found = [var for var in api_key_vars if os.getenv(var)]
    
    if api_keys_found:
        print(f"✓ API key(s) found: {', '.join(api_keys_found)}")
    else:
        print("❌ No API keys found")
        print("📋 Set at least one of: GEMINI_API_KEY, GOOGLE_API_KEY, API_KEY, API_KEY1, API_KEY2")
        print("📋 Get an API key from: https://ai.google.dev/gemini-api")
        all_good = False
    
    return all_good

def check_disk_space():
    """Check available disk space."""
    try:
        import shutil
        total, used, free = shutil.disk_usage(".")
        free_gb = free // (1024**3)
        
        if free_gb > 5:
            print(f"✓ Disk space: {free_gb}GB available")
            return True
        else:
            print(f"⚠️  Low disk space: {free_gb}GB available")
            print("📋 Consider freeing up space for temporary files")
            return False
    except Exception as e:
        print(f"⚠️  Could not check disk space: {e}")
        return False

def performance_recommendations():
    """Provide performance optimization recommendations."""
    print("\n🚀 Performance Recommendations:")
    print("1. Install Redis for production caching")
    print("2. Use a reverse proxy (nginx) for production")
    print("3. Monitor yt-dlp rate limiting")
    print("4. Keep yt-dlp updated regularly")
    print("5. Use environment-specific configuration")
    print("6. Implement proper logging and monitoring")

def main():
    """Run all system checks."""
    print("🔍 System Check for YouTube Video Processing App")
    print("=" * 50)
    
    checks = [
        ("Python Version", check_python_version),
        ("FFmpeg Installation", check_ffmpeg),
        ("Required Packages", check_required_packages),
        ("yt-dlp Version", check_yt_dlp_version),
        ("Cookies File", check_cookies_file),
        ("Environment Variables", check_environment_variables),
        ("Disk Space", check_disk_space),
    ]
    
    results = []
    
    for check_name, check_func in checks:
        print(f"\n🔍 Checking {check_name}:")
        result = check_func()
        results.append((check_name, result))
    
    print("\n" + "=" * 50)
    print("📊 Summary:")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for check_name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"   {check_name}: {status}")
    
    print(f"\n🎯 Score: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 All checks passed! Your system is ready.")
    else:
        print("⚠️  Some issues found. Please address them for optimal performance.")
    
    performance_recommendations()

if __name__ == "__main__":
    main()
