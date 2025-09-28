# Podcast Summarizer

CLI podcast summaries sent to email. 

```bash
# Simple one-line usage after setup
podcast "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

Uses:

- [OpenAI Whisper](https://github.com/openai/whisper) for transcription
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for media extraction
- [Anthropic Claude](https://anthropic.com) for AI summaries


## Usage

### Quick Start with CLI Alias

After installation, you can use the simple `podcast` command:

```bash
# Process any podcast URL
podcast "https://www.youtube.com/watch?v=..."

# Process without email
podcast "https://pca.st/episode/..." --no-email

# Process existing MP3
podcast --mp3 podcast.mp3

# Process existing transcript
podcast --transcript transcript.txt

# Force regeneration (skip cache)
podcast "url" --force

# Batch processing
podcast --batch audio_files/*.mp3
```

### Full Command Options

```bash
# Without alias - using Python directly
python3 podcast_summarizer.py "https://www.youtube.com/watch?v=..."

# Process without email
python3 podcast_summarizer.py "https://pca.st/episode/..." --no-email

# Process existing MP3
python3 podcast_summarizer.py --mp3 podcast.mp3

# Batch process all MP3s in audio_files/
python3 process_existing.py --all

# Enable verbose output
python3 podcast_summarizer.py --verbose "url"
```

### Supported Platforms

| Platform | Transcript | Audio | Notes |
|----------|------------|-------|-------|
| YouTube | Native | Yes | Auto-fetches captions when available |
| PocketCasts | No | Yes | Direct MP3 extraction |
| Spotify | No | Yes | Via yt-dlp |
| Direct MP3 | No | Yes | Any MP3 URL |

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