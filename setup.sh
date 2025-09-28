#!/bin/bash

# Podcast Summarizer Setup Script

echo "🎙️  Podcast Summarizer Setup"
echo "============================"
echo

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Install required packages
echo
echo "📦 Installing required packages..."
pip3 install --quiet --user requests beautifulsoup4 openai-whisper yt-dlp python-dotenv youtube-transcript-api

echo "✓ Packages installed"

# Create directories
echo
echo "📁 Creating directories..."
mkdir -p "$SCRIPT_DIR/audio_files" "$SCRIPT_DIR/transcripts" "$SCRIPT_DIR/summaries" "$SCRIPT_DIR/old_versions"

echo "✓ Directories created"

# Check for Claude Code
if [ -f "$HOME/.claude/local/claude" ]; then
    echo "✓ Claude Code detected"
else
    echo "⚠️  Claude Code not found - summaries will require manual generation"
    echo "   Install from: https://claude.ai"
fi

# Setup bash alias
echo
echo "🔧 Setting up command alias..."

SHELL_RC="$HOME/.zshrc"
if [ ! -f "$SHELL_RC" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

alias_line="alias podcast='python3 $SCRIPT_DIR/podcast_summarizer.py'"

if ! grep -q "alias podcast=" "$SHELL_RC" 2>/dev/null; then
    echo "" >> "$SHELL_RC"
    echo "# Podcast Summarizer" >> "$SHELL_RC"
    echo "$alias_line" >> "$SHELL_RC"
    echo "✓ Alias added to $SHELL_RC"
    echo
    echo "   Run this to activate:"
    echo "   source $SHELL_RC"
else
    echo "✓ Alias already exists"
fi

# Show usage
echo
echo "📖 Usage Examples:"
echo "  python3 podcast_summarizer.py https://pca.st/episode/abc123"
echo "  python3 podcast_summarizer.py --mp3 audio.mp3"
echo "  python3 process_existing.py --all"
echo
echo "  After sourcing your shell config:"
echo "  podcast https://www.youtube.com/watch?v=xyz"
echo

echo "✅ Setup complete!"