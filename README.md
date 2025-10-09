# Podcast Summarizer

Smart CLI tool that automatically transcribes and summarizes **any content** - podcasts, videos, articles, or local files.

```bash
# Just give it any input - it figures out what to do!
podcast "https://www.youtube.com/watch?v=..."  # Video
podcast "https://example.com/article"          # Article
podcast "video.mp4"                            # Local video
podcast "audio.mp3"                            # Local audio
```

Uses:

- [OpenAI Whisper](https://github.com/openai/whisper) for transcription
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for media extraction
- [Anthropic Claude](https://anthropic.com) for AI summaries


## Usage

### Automatic Content Detection

The tool automatically detects what you're processing:

```bash
# URLs - auto-detects type
podcast "https://www.youtube.com/watch?v=..."      # → Video (transcribe audio)
podcast "https://pca.st/episode/abc123"            # → Podcast (download & transcribe)
podcast "https://www.mckinsey.com/article"         # → Article (extract text)

# Local files - detects from extension
podcast "video.mp4"                                # → Video (extract audio & transcribe)
podcast "audio.mp3"                                # → Audio (transcribe)
podcast "transcript.txt"                           # → Transcript (summarize directly)

# Batch processing - auto-detects each file
podcast --batch media_files/*                      # Handles mixed types!

# Force specific mode if needed
podcast -t "https://example.com"                   # Force article mode
podcast --screenshots "https://youtube.com/..."    # Force screenshot analysis

# Add custom requests to any content
podcast -p "extract 4 linkedin quotes" "https://youtube.com/watch?v=..."
podcast -p "focus on technical details" "https://blog.example.com/post"
```

### How Auto-Detection Works

The tool automatically determines content type from:

1. **Local files** - by file extension:
   - Audio: `.mp3`, `.m4a`, `.wav`, `.aac`, `.flac`
   - Video: `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`
   - Text: `.txt`, `.md`

2. **URLs** - by pattern matching and HTTP headers:
   - YouTube/Vimeo links → Video
   - Podcast platforms (PocketCasts, Spotify) → Podcast
   - Other URLs → Checks HTTP Content-Type header
   - Default fallback → Article

### Supported Sources

| Type | Sources | Auto-Detect | Notes |
|------|---------|-------------|-------|
| **Video** | YouTube, Vimeo, local files | ✓ | Auto-fetches captions when available, otherwise transcribes |
| **Podcast** | PocketCasts, Spotify, direct MP3 URLs | ✓ | Direct download and transcription |
| **Audio** | Local `.mp3`, `.m4a`, `.wav`, `.aac`, `.flac` | ✓ | Transcribed with Whisper |
| **Article** | Any web page/blog | ✓ | Extracts and analyzes text content |
| **Transcript** | Local `.txt`, `.md` files | ✓ | Direct summarization |

## Configuration

### Personalization (Highly Recommended!)

Copy the example config and customize it with your details:

```bash
cp podcast_config.example.yaml podcast_config.yaml
nano podcast_config.yaml
```

Edit these key sections:
- **role**: Your role (founder/investor/engineer/etc.)
- **interests**: Topics you care about
- **goals**: What you want from podcasts
- **context**: Brief description of your situation


## Installation

### Prerequisites

- Python 3.8+
- [Claude Desktop App](https://claude.ai) (for AI summaries)
- FFmpeg (for audio processing)

### Quick Setup

```bash
# Clone the repository
git clone https://github.com/mattarderne/podcast.git
cd podcast

# Run setup script (this creates the 'podcast' command)
./setup.sh

# Activate the alias
source ~/.bashrc  # or source ~/.zshrc for macOS

# Now you can use the simple command
podcast "https://www.youtube.com/watch?v=..."
```


### Configuration

1. **Email Setup** (optional):

Create a `.env` file from the template:
```bash
cp .env.example .env
# Edit .env with your email settings
```

For Gmail users:
- Generate an [App Password](https://myaccount.google.com/apppasswords)
- Use the app password (not your regular password)

2. **Claude Setup**:
- Install [Claude Desktop](https://claude.ai)
- The tool will automatically detect and use it

## Summary Format

Each summary includes:

- **Key Points**: 7-10 specific insights with metrics and examples
- **Notable Quotes**: 5-7 memorable quotes with attribution
- **Founder Insights**: 2 tactical pieces of advice for entrepreneurs
- **People & References**: Key people, companies, and concepts mentioned
- **Main Takeaways**: 3-4 actionable lessons with context
- **Episode Summary**: Comprehensive paragraph capturing the narrative
- **Insight Rating**: Usefulness, novelty, and depth scores (1-10)
- **Topics**: Hashtags for categorization

## File Organization

```
podcast/
├── podcast_summarizer.py       # Main script
├── process_existing.py         # Batch processing
├── setup.sh                    # Installation script
├── requirements.txt            # Python dependencies
├── .env.example               # Email config template
├── audio_files/               # Downloaded podcasts
│   └── .gitkeep
├── transcripts/               # Whisper transcriptions
│   └── .gitkeep
└── summaries/                 # AI-generated summaries
    └── .gitkeep
```

Files are organized with consistent IDs:
- Format: `{platform}_{hash}_{date}`
- Example: `pca_6c0eb0b1_20250928`
- Makes it easy to find related audio, transcript, and summary files

## Advanced Features

### Article Processing

Process articles and web content with article-specific analysis:

```bash
# Basic article processing
podcast -t "https://www.example.com/article"

# With custom requests
podcast -t -p "summarize in bullet points" "https://blog.example.com/post"
```

Articles get a different analysis structure focused on:
- Key arguments and evidence
- Data and statistics
- Actionable takeaways
- Critical analysis
- Connections to current trends

### Custom Prompts

Add specific requests to any summary:

```bash
# For podcasts
podcast -p "extract 4 linkedin quotes" "https://youtube.com/watch?v=..."

# For articles
podcast -t -p "focus on implementation details" "https://blog.example.com"

# Multiple requests
podcast -p "get key metrics and create a twitter thread" "url"
```

### Batch Processing

```bash
# Process all MP3s in a directory
python3 process_existing.py --dir /path/to/podcasts

# Process with email disabled
python3 process_existing.py --all --no-email
```

### Email Features

When configured, emails include:
- **Subject**: "Summary: [Key Insight from Episode]"
- **Body**: Plain-text formatted summary (Gmail-optimized)
- **Attachment**: Full transcript as .txt file


Example:
```
💡 CORE INSIGHT:
[The single most valuable takeaway]

✅ USEFUL BECAUSE:
[Why this matters for your specific context]

🎯 MAIN TAKEAWAYS
[Actionable items with spacing]

🔍 PEOPLE & COMPANIES
- Tom Tunguz: Partner at Theory Ventures
  → Search: https://www.google.com/search?q=Tom+Tunguz
```


## Troubleshooting

**Claude not found**:
- Install Claude Desktop from [claude.ai](https://claude.ai)

**Whisper fails**:
- Ensure FFmpeg is installed: `brew install ffmpeg` (macOS)

**Email not sending**:
- Check `.env` configuration
- For Gmail, ensure you're using an App Password

**Slow processing**:
- First run downloads Whisper model (~1GB)
- Transcription speed depends on CPU

## Contributing

Contributions welcome! To contribute:

1. Fork the repository
2. Create a feature branch
3. Test with the sample URL:
   ```
   https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.


## Disclaimer

This tool is for personal use. Respect copyright laws and podcast creators' rights. Only process content you have permission to use.