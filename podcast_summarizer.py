#!/usr/bin/env python3
"""
Podcast Summarizer - Clean Version
Automatically downloads, transcribes, and summarizes podcasts with organized output
"""

import hashlib
import json
import logging
import os
import re
import smtplib
import subprocess
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class PodcastProcessor:
    """Main processor for podcast summarization"""

    def __init__(self, base_dir: Path = Path.cwd(), enable_email: bool = True):
        """Initialize with organized directory structure"""
        self.base_dir = base_dir
        self.audio_dir = base_dir / "audio_files"
        self.transcript_dir = base_dir / "transcripts"
        self.summary_dir = base_dir / "summaries"
        self.enable_email = enable_email

        # Create directories
        for directory in [self.audio_dir, self.transcript_dir, self.summary_dir]:
            directory.mkdir(exist_ok=True)

        # Claude Code path
        self.claude_path = Path.home() / '.claude' / 'local' / 'claude'
        if not self.claude_path.exists():
            logger.error("Claude Code not found. Please install Claude Code.")
            sys.exit(1)

        # Load email configuration if enabled
        self.email_config = None
        if self.enable_email:
            self.email_config = self.load_email_config()

    def generate_id(self, url: str) -> str:
        """Generate consistent ID for a URL"""
        # Clean URL for consistent hashing
        clean_url = re.sub(r'[?&]utm_[^&]*', '', url)  # Remove UTM parameters
        clean_url = clean_url.rstrip('/')

        # Generate short hash
        url_hash = hashlib.md5(clean_url.encode()).hexdigest()[:8]

        # Add timestamp for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d")

        # Create readable ID with domain hint
        domain = urlparse(url).netloc.replace('www.', '').split('.')[0][:10]

        return f"{domain}_{url_hash}_{timestamp}"

    def get_existing_files(self, podcast_id: str) -> Dict[str, Optional[Path]]:
        """Check for existing files with this ID"""
        return {
            'audio': self.find_file(self.audio_dir, f"{podcast_id}*.mp3"),
            'transcript': self.find_file(self.transcript_dir, f"{podcast_id}*.txt"),
            'summary': self.find_file(self.summary_dir, f"{podcast_id}*.md")
        }

    def find_file(self, directory: Path, pattern: str) -> Optional[Path]:
        """Find first file matching pattern"""
        files = list(directory.glob(pattern))
        return files[0] if files else None

    def fetch_transcript(self, url: str) -> Optional[str]:
        """Try to fetch existing transcript from platform"""
        # YouTube transcripts
        if 'youtube.com' in url or 'youtu.be' in url:
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
                video_id = self.extract_youtube_id(url)
                if video_id:
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                    return ' '.join([t['text'] for t in transcript_list])
            except Exception as e:
                logger.debug(f"No YouTube transcript: {e}")

        # Add other platform checks here if needed
        return None

    def extract_youtube_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?]*)',
            r'youtube\.com\/embed\/([^&\n?]*)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def download_audio(self, url: str, podcast_id: str) -> Optional[Path]:
        """Download audio from URL"""
        output_path = self.audio_dir / f"{podcast_id}.mp3"

        # Try direct MP3 extraction for PocketCasts
        if 'pca.st' in url or 'pocketcasts.com' in url:
            mp3_url = self.extract_pocketcasts_url(url)
            if mp3_url:
                return self.download_mp3(mp3_url, output_path)

        # Use yt-dlp for other platforms
        return self.download_with_ytdlp(url, output_path)

    def extract_pocketcasts_url(self, url: str) -> Optional[str]:
        """Extract direct MP3 URL from PocketCasts"""
        try:
            cmd = ['sh', '-c', f'curl -s -L "{url}" | grep -oE "https://[^\\"]*\\.mp3[^\\"]*" | head -1']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"PocketCasts extraction failed: {e}")
        return None

    def download_mp3(self, mp3_url: str, output_path: Path) -> Optional[Path]:
        """Download MP3 file with progress"""
        try:
            response = requests.get(mp3_url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            progress = (downloaded / total_size) * 100
                            print(f'\rDownloading: {progress:.1f}%', end='', flush=True)

            print()  # New line after progress
            logger.info(f"Audio saved: {output_path.name}")
            return output_path

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None

    def download_with_ytdlp(self, url: str, output_path: Path) -> Optional[Path]:
        """Download using yt-dlp"""
        try:
            import yt_dlp
        except ImportError:
            logger.info("Installing yt-dlp...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'yt-dlp'], check=True)
            import yt_dlp

        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(output_path.with_suffix('')),  # Remove .mp3 as yt-dlp adds it
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Check if file was created
            if output_path.exists():
                logger.info(f"Audio saved: {output_path.name}")
                return output_path

        except Exception as e:
            logger.error(f"yt-dlp download failed: {e}")

        return None

    def transcribe_audio(self, audio_path: Path, podcast_id: str) -> Optional[str]:
        """Transcribe audio using Whisper"""
        transcript_path = self.transcript_dir / f"{podcast_id}.txt"
        json_path = self.transcript_dir / f"{podcast_id}.json"

        # Check if transcript already exists
        if transcript_path.exists():
            logger.info(f"Using cached transcript: {transcript_path.name}")
            return transcript_path.read_text(encoding='utf-8')

        try:
            import whisper
        except ImportError:
            logger.info("Installing OpenAI Whisper...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'openai-whisper'], check=True)
            import whisper

        try:
            logger.info("Loading Whisper model...")
            model = whisper.load_model("base")

            logger.info("Transcribing audio (this may take a few minutes)...")
            result = model.transcribe(str(audio_path))

            # Save transcript
            transcript_path.write_text(result['text'], encoding='utf-8')
            json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')

            logger.info(f"Transcript saved: {transcript_path.name}")
            return result['text']

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None

    def summarize_transcript(self, transcript: str, podcast_id: str, url: str) -> str:
        """Generate summary using Claude"""
        summary_path = self.summary_dir / f"{podcast_id}.md"

        # Check if summary already exists
        if summary_path.exists():
            logger.info(f"Using cached summary: {summary_path.name}")
            return summary_path.read_text(encoding='utf-8')

        prompt = f"""Analyze this podcast transcript and create a comprehensive summary with specific, actionable insights.

First, provide:
PODCAST_NAME: [Name of the podcast/show]
TITLE: [Extract the main topic or most compelling insight as a title]
EPISODE_INFO: [Guest name(s) and their role/company]
TWO_LINE_SUMMARY: [2 sentence overview capturing the core value and unique perspective of this episode]

Then create these sections:

## Key Points (7-10 specific points with details)
• Include concrete examples, metrics, and specific strategies mentioned
• Each point should provide actionable detail, not generic statements
• Focus on unique insights rather than obvious observations

## Notable Quotes (5-7 memorable quotes)
• Direct quotes that capture pivotal moments or unique perspectives
• Include context and speaker attribution
• Focus on counterintuitive or particularly insightful statements

## Founder Insights
Identify 2 specific pieces of information that would be particularly valuable for founders/entrepreneurs:
• Focus on tactical advice, non-obvious lessons, or specific strategies
• Include details about implementation or results mentioned

## People, Companies & References
• Key people: name, role, and why they're relevant to the discussion
• Companies mentioned: what they do and why they were referenced
• Books, frameworks, or concepts: brief explanation of each

## Main Takeaways (3-4 detailed lessons)
• Actionable insights with enough context to implement
• Include any frameworks or mental models discussed
• Connect to broader themes or principles

## Episode Summary
A comprehensive paragraph (7-10 sentences) that captures the narrative arc, key turning points in the conversation, and the unique value this episode provides. Include specific examples or stories that were discussed.

## Insight Rating
Rate this podcast episode on three dimensions (1-10 scale):
• Usefulness: How actionable and practical are the insights?
• Novelty: How unique or counterintuitive is the information?
• Depth: How thoroughly were topics explored with specific examples?
Overall Assessment: [Brief explanation of the rating]

## Topics
Relevant hashtags and categories for discovery

Transcript:
{transcript[:50000]}"""

        try:
            logger.info("Generating summary with Claude...")
            result = subprocess.run(
                [str(self.claude_path), '--print', prompt],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes for comprehensive summaries
            )

            if result.returncode == 0 and result.stdout:
                summary = result.stdout.strip()

                # Add metadata header
                header = f"""---
ID: {podcast_id}
URL: {url}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
---

"""
                full_summary = header + summary

                # Save summary
                summary_path.write_text(full_summary, encoding='utf-8')
                logger.info(f"Summary saved: {summary_path.name}")

                return full_summary
            else:
                logger.error(f"Claude error: {result.stderr}")
                return "Summary generation failed"

        except subprocess.TimeoutExpired:
            logger.error("Claude summarization timed out")
            return "Summary generation timed out"
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return f"Summary generation failed: {e}"

    def load_email_config(self) -> Optional[Dict[str, str]]:
        """Load email configuration from .env file"""
        env_file = self.base_dir / '.env'

        # Try .env file first
        if env_file.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file)
            except ImportError:
                logger.debug("python-dotenv not installed, reading .env manually")
                # Manual .env parsing
                with open(env_file, 'r') as f:
                    for line in f:
                        if '=' in line and not line.strip().startswith('#'):
                            key, value = line.strip().split('=', 1)
                            os.environ[key] = value.strip('"').strip("'")

        # Get configuration from environment
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = os.getenv('SMTP_PORT', '587')
        email_from = os.getenv('EMAIL_FROM')
        email_password = os.getenv('EMAIL_PASSWORD')
        email_to = os.getenv('EMAIL_TO')

        if all([smtp_server, email_from, email_password, email_to]):
            return {
                'smtp_server': smtp_server,
                'smtp_port': int(smtp_port),
                'email_from': email_from,
                'email_password': email_password,
                'email_to': email_to
            }

        logger.info("Email configuration not found or incomplete. Email sending disabled.")
        logger.info("To enable email, create a .env file with:")
        logger.info("  SMTP_SERVER=smtp.gmail.com")
        logger.info("  SMTP_PORT=587")
        logger.info("  EMAIL_FROM=your-email@gmail.com")
        logger.info("  EMAIL_PASSWORD=your-app-password")
        logger.info("  EMAIL_TO=recipient@example.com")
        return None

    def format_email_body(self, summary: str, url: str = None) -> str:
        """Format summary for plain text email (Gmail-friendly)"""
        lines = summary.split('\n')
        formatted = []

        # Extract metadata from summary
        podcast_name = None
        title = None
        episode_info = None
        two_line = None

        for line in lines:
            if line.startswith('PODCAST_NAME:'):
                podcast_name = line.replace('PODCAST_NAME:', '').strip()
            elif line.startswith('TITLE:'):
                title = line.replace('TITLE:', '').strip()
            elif line.startswith('EPISODE_INFO:'):
                episode_info = line.replace('EPISODE_INFO:', '').strip()
            elif line.startswith('TWO_LINE_SUMMARY:'):
                two_line = line.replace('TWO_LINE_SUMMARY:', '').strip()

        # Add header
        if podcast_name:
            formatted.append(f"PODCAST: {podcast_name}")
        if episode_info:
            formatted.append(f"GUEST: {episode_info}")
        if url:
            formatted.append(f"LINK: {url}")
        if two_line:
            formatted.append(f"\nSUMMARY:\n{two_line}")

        formatted.append("\n" + "="*60 + "\n")

        # Process rest of summary
        in_section = False
        for line in lines:
            # Skip the extracted header lines
            if line.startswith(('PODCAST_NAME:', 'TITLE:', 'EPISODE_INFO:', 'TWO_LINE_SUMMARY:')):
                continue

            # Convert markdown headers to plain text sections
            if line.startswith('## '):
                formatted.append("\n" + line.replace('## ', '').upper())
                formatted.append("-" * 40)
                in_section = True
            elif line.startswith('# '):
                continue  # Skip main header
            elif line.strip():
                # Remove markdown formatting
                clean_line = line.replace('**', '').replace('*', '').replace('•', '-')
                formatted.append(clean_line)

        return '\n'.join(formatted)

    def send_email(self, subject: str, body: str, url: str = None, transcript_path: Path = None) -> bool:
        """Send email with summary and optional transcript attachment"""
        if not self.email_config:
            return False

        try:
            # Extract title from summary for better subject
            title = None
            for line in body.split('\n'):
                if line.startswith('TITLE:'):
                    title = line.replace('TITLE:', '').strip()
                    break

            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_config['email_from']
            msg['To'] = self.email_config['email_to']

            # Use title in subject if found
            if title:
                msg['Subject'] = f"Summary: {title}"
            else:
                msg['Subject'] = subject

            # Format body for plain text email
            formatted_body = self.format_email_body(body, url)
            msg.attach(MIMEText(formatted_body, 'plain'))

            # Attach transcript if available
            if transcript_path and transcript_path.exists():
                with open(transcript_path, 'rb') as f:
                    part = MIMEBase('text', 'plain')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="transcript_{transcript_path.stem}.txt"'
                    )
                    msg.attach(part)

            # Send email
            with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port']) as server:
                server.starttls()
                server.login(self.email_config['email_from'], self.email_config['email_password'])
                server.send_message(msg)

            logger.info(f"Summary emailed to {self.email_config['email_to']}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def process_url(self, url: str) -> Dict[str, any]:
        """Process a podcast URL"""
        logger.info(f"Processing: {url}")

        # Generate consistent ID
        podcast_id = self.generate_id(url)
        logger.info(f"Podcast ID: {podcast_id}")

        # Check existing files
        existing = self.get_existing_files(podcast_id)

        # Get transcript (from cache, platform, or transcription)
        transcript = None

        if existing['transcript']:
            logger.info(f"Found existing transcript: {existing['transcript'].name}")
            transcript = existing['transcript'].read_text(encoding='utf-8')
        else:
            # Try to fetch platform transcript
            transcript = self.fetch_transcript(url)

            if transcript:
                logger.info("Using platform transcript")
                # Save fetched transcript
                transcript_path = self.transcript_dir / f"{podcast_id}.txt"
                transcript_path.write_text(transcript, encoding='utf-8')
            else:
                # Download and transcribe
                audio_path = existing['audio']

                if not audio_path:
                    logger.info("Downloading audio...")
                    audio_path = self.download_audio(url, podcast_id)

                if audio_path:
                    transcript = self.transcribe_audio(audio_path, podcast_id)

        if not transcript:
            logger.error("Failed to obtain transcript")
            return {'success': False, 'error': 'Could not obtain transcript'}

        # Generate or use existing summary
        if existing['summary']:
            logger.info(f"Found existing summary: {existing['summary'].name}")
            summary = existing['summary'].read_text(encoding='utf-8')
        else:
            summary = self.summarize_transcript(transcript, podcast_id, url)

        # Send email if configured
        if self.enable_email and self.email_config:
            transcript_file = self.transcript_dir / f"{podcast_id}.txt"
            subject = f"Podcast Summary - {podcast_id}"
            self.send_email(subject, summary, url, transcript_file)

        return {
            'success': True,
            'id': podcast_id,
            'url': url,
            'transcript_file': self.transcript_dir / f"{podcast_id}.txt",
            'summary_file': self.summary_dir / f"{podcast_id}.md",
            'summary': summary,
            'email_sent': self.email_config is not None
        }

    def process_mp3(self, mp3_path: Path) -> Dict[str, any]:
        """Process an existing MP3 file"""
        logger.info(f"Processing MP3: {mp3_path}")

        # Generate ID from filename
        podcast_id = mp3_path.stem

        # Transcribe
        transcript = self.transcribe_audio(mp3_path, podcast_id)

        if not transcript:
            return {'success': False, 'error': 'Transcription failed'}

        # Summarize
        summary = self.summarize_transcript(transcript, podcast_id, str(mp3_path))

        # Send email if configured
        if self.enable_email and self.email_config:
            transcript_file = self.transcript_dir / f"{podcast_id}.txt"
            subject = f"Podcast Summary - {mp3_path.name}"
            self.send_email(subject, summary, str(mp3_path), transcript_file)

        return {
            'success': True,
            'id': podcast_id,
            'mp3_file': mp3_path,
            'transcript_file': self.transcript_dir / f"{podcast_id}.txt",
            'summary_file': self.summary_dir / f"{podcast_id}.md",
            'summary': summary,
            'email_sent': self.email_config is not None
        }


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Download, transcribe, and summarize podcasts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://pca.st/episode/abc123
  %(prog)s --mp3 audio.mp3
  %(prog)s --batch audio_files/*.mp3
        """
    )

    parser.add_argument('url', nargs='?', help='Podcast URL to process')
    parser.add_argument('--mp3', help='Process existing MP3 file')
    parser.add_argument('--batch', nargs='+', help='Process multiple files')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser.add_argument('--no-email', action='store_true', help='Disable email sending')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize processor
    processor = PodcastProcessor(enable_email=not args.no_email)

    # Process based on input
    if args.batch:
        # Batch processing
        for file_pattern in args.batch:
            for file_path in Path().glob(file_pattern):
                if file_path.suffix.lower() in ['.mp3', '.m4a', '.wav']:
                    result = processor.process_mp3(file_path)
                    if result['success']:
                        print(f"\n{'='*60}")
                        print(f"✅ Processed: {file_path.name}")
                        print(f"   ID: {result['id']}")
                        print(f"   Summary: {result['summary_file']}")

    elif args.mp3:
        # Single MP3
        mp3_path = Path(args.mp3)
        if not mp3_path.exists():
            logger.error(f"File not found: {args.mp3}")
            sys.exit(1)

        result = processor.process_mp3(mp3_path)
        if result['success']:
            print(f"\n{'='*60}")
            print(result['summary'])
            print(f"{'='*60}\n")
            print(f"Files saved:")
            print(f"  Transcript: {result['transcript_file']}")
            print(f"  Summary: {result['summary_file']}")
            if result.get('email_sent'):
                print(f"  Email: Sent to {processor.email_config['email_to']}")
            elif not args.no_email:
                print(f"  Email: Not configured (see .env.example)")

    elif args.url:
        # URL processing
        result = processor.process_url(args.url)
        if result['success']:
            print(f"\n{'='*60}")
            print(result['summary'])
            print(f"{'='*60}\n")
            print(f"Files saved:")
            print(f"  Transcript: {result['transcript_file']}")
            print(f"  Summary: {result['summary_file']}")
            if result.get('email_sent'):
                print(f"  Email: Sent to {processor.email_config['email_to']}")
            elif not args.no_email:
                print(f"  Email: Not configured (see .env.example)")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()