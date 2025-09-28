# Podcast Summarizer

An automated tool that downloads, transcribes, and generates AI-powered summaries of podcasts with email delivery.

## Features

- **Multi-Platform Support**: Works with YouTube, PocketCasts, Spotify, and direct MP3 URLs
- **Automatic Transcription**: Uses OpenAI Whisper for high-quality audio-to-text conversion
- **AI Summaries**: Generates comprehensive summaries using Claude API
- **Smart Caching**: Avoids re-processing with intelligent file detection
- **Email Delivery**: Sends formatted summaries with transcript attachments
- **Batch Processing**: Handle multiple podcast files at once
- **Founder Insights**: Extracts specific insights valuable for entrepreneurs

## Usage

### Basic Commands

```bash
# Process a podcast URL
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

# Run setup script
./setup.sh

# Or manual installation
pip install -r requirements.txt
mkdir -p audio_files transcripts summaries
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

### Performance

- **Whisper Model**: Base model (balanced speed/accuracy)
- **Processing Time**: ~2-5 minutes for 30-minute podcast
- **Transcript Limit**: 50,000 characters sent to Claude
- **Storage**: ~30MB per podcast (audio + transcript + summary)

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

## Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) for transcription
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for media extraction
- [Anthropic Claude](https://anthropic.com) for AI summaries

## Disclaimer

This tool is for personal use. Respect copyright laws and podcast creators' rights. Only process content you have permission to use.