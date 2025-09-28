#!/bin/bash

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Install required packages silently
pip3 install --quiet --user requests beautifulsoup4 openai-whisper yt-dlp python-dotenv youtube-transcript-api 2>/dev/null

# Create directories silently
mkdir -p "$SCRIPT_DIR/audio_files" "$SCRIPT_DIR/transcripts" "$SCRIPT_DIR/summaries" 2>/dev/null

# Setup bash alias
SHELL_RC="$HOME/.zshrc"
if [ ! -f "$SHELL_RC" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

alias_line="alias podcast='python3 $SCRIPT_DIR/podcast_summarizer.py'"

if ! grep -q "alias podcast=" "$SHELL_RC" 2>/dev/null; then
    echo "" >> "$SHELL_RC"
    echo "# Podcast Summarizer" >> "$SHELL_RC"
    echo "$alias_line" >> "$SHELL_RC"
fi

# Output only essential info
echo "Setup complete!"
echo ""
echo "1. Activate the command:"
echo "   source $SHELL_RC"
echo ""
echo "2. Use:"
echo "   podcast \"https://www.youtube.com/watch?v=...\""