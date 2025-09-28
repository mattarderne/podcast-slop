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
import yaml
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
    level=logging.WARNING,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


class PodcastProcessor:
    """Main processor for podcast summarization"""

    def __init__(self, base_dir: Path = None, enable_email: bool = True, force_regenerate: bool = False, model: str = None):
        """Initialize with organized directory structure"""
        # Always use script directory as base to ensure consistent file locations
        self.script_dir = Path(__file__).parent
        self.base_dir = base_dir if base_dir else self.script_dir
        self.audio_dir = self.base_dir / "audio_files"
        self.transcript_dir = self.base_dir / "transcripts"
        self.summary_dir = self.base_dir / "summaries"
        self.enable_email = enable_email
        self.force_regenerate = force_regenerate
        self.model = model

        # Load unified configuration
        self.config = self.load_unified_config()

        # Create directories
        for directory in [self.audio_dir, self.transcript_dir, self.summary_dir]:
            directory.mkdir(exist_ok=True)

        # Claude Code path - with model selection
        self.claude_path = self.get_claude_command()

        # Load email configuration if enabled
        self.email_config = None
        if self.enable_email:
            self.email_config = self.load_email_config()

    def load_unified_config(self) -> Dict:
        """Load unified configuration from podcast_config.yaml"""
        config_path = self.script_dir / 'podcast_config.yaml'

        # Try to load the new unified config
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    print(f"✓ Loaded config for {config.get('profile', {}).get('role', 'user')}")
                    return config
            except Exception as e:
                print(f"Warning: Could not load podcast_config.yaml: {e}")

        # Fallback: Try old config files for backwards compatibility
        old_config_path = self.script_dir / 'config.yaml'
        if old_config_path.exists():
            try:
                with open(old_config_path, 'r') as f:
                    old_config = yaml.safe_load(f)
                    # Convert old format to new format
                    return {
                        'profile': {
                            'role': old_config.get('role', 'general'),
                            'interests': old_config.get('interests', []),
                            'goals': old_config.get('goals', []),
                            'context': old_config.get('context', '')
                        },
                        'preferences': old_config.get('preferences', {})
                    }
            except:
                pass

        # Return default config if no files exist
        return {
            'profile': {
                'role': 'general',
                'interests': [],
                'goals': [],
                'context': ''
            },
            'preferences': {
                'critical_rating': True,
                'emphasis': 'actionable'
            }
        }

    def get_claude_command(self) -> Path:
        """Get Claude command with optional model selection"""
        base_path = Path.home() / '.claude' / 'local' / 'claude'

        if not base_path.exists():
            print("Error: Claude Code not found. Please install Claude Code.")
            sys.exit(1)

        # Note: Claude Code CLI currently doesn't support model selection via command line
        # This is prepared for future API usage or when the feature is added
        # For now, it uses whatever model Claude Code is configured with

        return base_path

    def get_default_prompts(self) -> Dict:
        """Get default prompts if prompts.yaml is missing"""
        # Default prompts when no config file exists
        summary_prompt = """Analyze this podcast transcript and create a comprehensive summary with specific, actionable insights.

First, provide:
PODCAST_NAME: [Name of the podcast/show]
TITLE: [Extract the main topic or most compelling insight as a title]
EPISODE_INFO: [Guest name(s) and their role/company]

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

## Critical Analysis & Rating
Be intellectually honest and critical. Rate this podcast episode on three dimensions (1-10 scale):
• Usefulness: Are the insights actually actionable or just platitudes? Do they provide specific steps?
• Novelty: Is this genuinely new information or recycled conventional wisdom? What's truly counterintuitive?
• Depth: Did they explore root causes and second-order effects, or stay surface-level? Were hard questions asked?

Weaknesses: [What important topics were glossed over? What claims lacked evidence?]
Strengths: [What genuine insights or unique perspectives were shared?]
Overall Assessment: [Be critical - most podcasts should score 4-7, not 8-10]

## Topics
Relevant hashtags and categories for discovery

Transcript:
{transcript}"""

        synthesis_prompt = """Based on this podcast summary, synthesize the most important insights or takeaways.

Summary:
{summary}

Provide:
CORE_INSIGHT: [One sentence that captures the non-obvious, most valuable insights from this conversation - be specific, not generic]
USEFUL_BECAUSE: [2-3 sentences explaining why this insight matters and how it can be applied practically. What specific problem does it solve or opportunity does it create?]

Be intellectually rigorous - focus on what's genuinely valuable, not what sounds impressive."""

        return {
            'summary_prompt': summary_prompt,
            'synthesis_prompt': synthesis_prompt
        }

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
                pass  # No transcript available from YouTube

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
                            # Silently update progress

            # Download complete
            print(f"✓ Audio downloaded")
            return output_path

        except Exception as e:
            print(f"Error: Download failed - {e}")
            return None

    def download_with_ytdlp(self, url: str, output_path: Path) -> Optional[Path]:
        """Download using yt-dlp"""
        try:
            import yt_dlp
        except ImportError:
            print("Installing yt-dlp...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'yt-dlp'], check=True, capture_output=True)
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
                'noprogress': True,
                'postprocessor_args': {
                    'FFmpegExtractAudio': ['-loglevel', 'quiet']
                }
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Check if file was created
            if output_path.exists():
                print(f"✓ Audio downloaded")
                return output_path

        except Exception as e:
            print(f"Error: Download failed - {e}")

        return None

    def transcribe_audio(self, audio_path: Path, podcast_id: str) -> Optional[str]:
        """Transcribe audio using Whisper"""
        transcript_path = self.transcript_dir / f"{podcast_id}.txt"

        # Check if transcript already exists
        if transcript_path.exists():
            print(f"✓ Using cached transcript")
            return transcript_path.read_text(encoding='utf-8')

        try:
            import whisper
        except ImportError:
            print("Installing OpenAI Whisper...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'openai-whisper'], check=True, capture_output=True)
            import whisper

        try:
            print("Transcribing audio (this may take a few minutes)...")
            # Suppress Whisper warnings about FP16 on CPU
            import warnings
            warnings.filterwarnings("ignore", category=UserWarning, module="whisper")
            model = whisper.load_model("base")
            result = model.transcribe(str(audio_path))

            # Save transcript (text only, no metadata)
            transcript_path.write_text(result['text'], encoding='utf-8')

            print(f"✓ Transcript saved")
            return result['text']

        except Exception as e:
            print(f"Error: Transcription failed - {e}")
            return None

    def summarize_transcript(self, transcript: str, podcast_id: str, url: str) -> str:
        """Generate summary using Claude"""
        summary_path = self.summary_dir / f"{podcast_id}.md"

        # Check if summary already exists (unless force regenerate)
        if summary_path.exists() and not self.force_regenerate:
            print(f"✓ Using cached summary")
            return summary_path.read_text(encoding='utf-8')

        # Get prompt template (use default since prompts are now internal)
        prompt_template = self.get_default_prompts()['summary_prompt']

        # Prepare context variables from unified config
        profile = self.config.get('profile', {})
        user_context = profile.get('context', '')
        user_role = profile.get('role', 'general')
        user_interests = ', '.join(profile.get('interests', []))
        user_goals = '; '.join(profile.get('goals', []))

        # Replace placeholders in prompt template
        prompt = prompt_template.replace('{user_context}', user_context)
        prompt = prompt.replace('{user_role}', user_role)
        prompt = prompt.replace('{user_interests}', user_interests)
        prompt = prompt.replace('{user_goals}', user_goals)
        prompt = prompt.replace('{transcript}', transcript[:50000])

        try:
            print("Generating summary with Claude...")
            result = subprocess.run(
                [str(self.claude_path), '--print', prompt],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes for comprehensive summaries
            )

            if result.returncode == 0 and result.stdout:
                initial_summary = result.stdout.strip()

                # Second stage: Synthesize the core insight
                synthesis_template = self.get_default_prompts()['synthesis_prompt']

                # Replace placeholders in synthesis prompt
                synthesis_prompt = synthesis_template.replace('{user_context}', user_context)
                synthesis_prompt = synthesis_prompt.replace('{user_role}', user_role)
                synthesis_prompt = synthesis_prompt.replace('{user_interests}', user_interests)
                synthesis_prompt = synthesis_prompt.replace('{user_goals}', user_goals)
                synthesis_prompt = synthesis_prompt.replace('{summary}', initial_summary)

                print("Synthesizing core insight...")
                synthesis_result = subprocess.run(
                    [str(self.claude_path), '--print', synthesis_prompt],
                    capture_output=True,
                    text=True,
                    timeout=60  # 1 minute for synthesis
                )

                synthesis = ""
                if synthesis_result.returncode == 0 and synthesis_result.stdout:
                    synthesis = synthesis_result.stdout.strip() + "\n\n"

                # Add metadata header
                header = f"""---
ID: {podcast_id}
URL: {url}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
---

"""
                full_summary = header + synthesis + initial_summary

                # Save summary with synthesis
                summary_path.write_text(full_summary, encoding='utf-8')
                print(f"✓ Summary generated with core insight")

                return full_summary
            else:
                print(f"Error: Claude failed - {result.stderr}")
                return "Summary generation failed"

        except subprocess.TimeoutExpired:
            print("Error: Claude summarization timed out (5 minute limit)")
            return "Summary generation timed out"
        except Exception as e:
            print(f"Error: Summarization failed - {e}")
            return f"Summary generation failed: {e}"

    def load_email_config(self) -> Optional[Dict[str, str]]:
        """Load email configuration from .env file"""
        # Always look for .env in the script's directory
        env_file = self.script_dir / '.env'

        # Try .env file first
        if env_file.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file)
            except ImportError:
                # python-dotenv not installed, reading .env manually
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

        # Email not configured
        return None

    def extract_summary_metadata(self, summary: str) -> Dict[str, str]:
        """Extract metadata from summary for display"""
        metadata = {
            'podcast_name': '',
            'title': '',
            'episode_info': '',
            'core_insight': '',
            'useful_because': ''
        }

        lines = summary.split('\n')
        capture_next_lines = False
        useful_lines = []

        for line in lines:
            if line.startswith('PODCAST_NAME:'):
                metadata['podcast_name'] = line.replace('PODCAST_NAME:', '').strip()
            elif line.startswith('TITLE:'):
                metadata['title'] = line.replace('TITLE:', '').strip()
            elif line.startswith('EPISODE_INFO:'):
                metadata['episode_info'] = line.replace('EPISODE_INFO:', '').strip()
            elif line.startswith('CORE_INSIGHT:'):
                metadata['core_insight'] = line.replace('CORE_INSIGHT:', '').strip()
            elif line.startswith('USEFUL_BECAUSE:'):
                useful_text = line.replace('USEFUL_BECAUSE:', '').strip()
                if useful_text:
                    metadata['useful_because'] = useful_text
                else:
                    capture_next_lines = True
            elif capture_next_lines and line.strip() and not line.startswith('#'):
                useful_lines.append(line.strip())
                if len(useful_lines) >= 3 or not line.strip():
                    capture_next_lines = False

        if useful_lines and not metadata['useful_because']:
            metadata['useful_because'] = ' '.join(useful_lines)

        return metadata

    def format_email_body(self, summary: str, url: str = None) -> str:
        """Format summary for plain text email (Gmail-friendly with better spacing)"""
        import urllib.parse
        lines = summary.split('\n')
        formatted = []

        # Extract all metadata first
        metadata = {}
        content_sections = {}
        current_section = None
        section_content = []

        for line in lines:
            # Extract metadata
            if line.startswith('PODCAST_NAME:'):
                metadata['podcast_name'] = line.replace('PODCAST_NAME:', '').strip()
            elif line.startswith('TITLE:'):
                metadata['title'] = line.replace('TITLE:', '').strip()
            elif line.startswith('EPISODE_INFO:'):
                metadata['episode_info'] = line.replace('EPISODE_INFO:', '').strip()
            elif line.startswith('CORE_INSIGHT:'):
                metadata['core_insight'] = line.replace('CORE_INSIGHT:', '').strip()
            elif line.startswith('USEFUL_BECAUSE:'):
                metadata['useful_because'] = line.replace('USEFUL_BECAUSE:', '').strip()
            # Capture sections
            elif line.startswith('## '):
                if current_section and section_content:
                    content_sections[current_section] = section_content
                current_section = line.replace('## ', '').strip()
                section_content = []
            elif current_section and line.strip():
                section_content.append(line)

        # Save last section
        if current_section and section_content:
            content_sections[current_section] = section_content

        # BUILD EMAIL IN OPTIMAL ORDER FOR SKIMMING

        # 1. Header with key metadata
        formatted.append("="*60)
        if metadata.get('podcast_name'):
            formatted.append(f"PODCAST: {metadata['podcast_name']}")
        if metadata.get('episode_info'):
            formatted.append(f"GUEST: {metadata['episode_info']}")
        if url:
            formatted.append(f"LINK: {url}")
        formatted.append("="*60 + "\n")

        # 2. CORE INSIGHT (Most important - at top)
        if metadata.get('core_insight'):
            formatted.append("💡 CORE INSIGHT:")
            formatted.append(metadata['core_insight'])
            formatted.append("")

        if metadata.get('useful_because'):
            formatted.append("✅ USEFUL BECAUSE:")
            formatted.append(metadata['useful_because'])
            formatted.append("\n" + "="*60 + "\n")

        # 3. KEY TAKEAWAYS (Actionable items)
        if 'Main Takeaways' in content_sections:
            formatted.append("🎯 MAIN TAKEAWAYS")
            formatted.append("-" * 40)
            for line in content_sections['Main Takeaways']:
                clean_line = line.replace('**', '').replace('*', '').replace('•', '-')
                formatted.append(clean_line)
                formatted.append("")  # Extra space between items
            formatted.append("")

        # 4. NOTABLE QUOTES (Memorable)
        if 'Notable Quotes' in content_sections:
            formatted.append("💬 NOTABLE QUOTES")
            formatted.append("-" * 40)
            for line in content_sections['Notable Quotes']:
                clean_line = line.replace('**', '').replace('*', '').replace('•', '"')
                formatted.append(clean_line)
                formatted.append("")  # Extra space between quotes
            formatted.append("")

        # 5. KEY POINTS (Detailed insights)
        if 'Key Points' in content_sections:
            formatted.append("📌 KEY POINTS")
            formatted.append("-" * 40)
            for line in content_sections['Key Points']:
                clean_line = line.replace('**', '').replace('*', '').replace('•', '-')
                formatted.append(clean_line)
                formatted.append("")  # Extra space between points
            formatted.append("")

        # 6. PEOPLE & COMPANIES WITH SEARCH LINKS
        if 'People, Companies & References' in content_sections:
            formatted.append("🔍 PEOPLE, COMPANIES & REFERENCES")
            formatted.append("-" * 40)
            for line in content_sections['People, Companies & References']:
                clean_line = line.replace('**', '').replace('*', '').replace('•', '-')

                # Add Google search link for each entity
                if ':' in clean_line and not clean_line.startswith('http'):
                    entity = clean_line.split(':')[0].strip(' -•')
                    if entity:
                        search_query = urllib.parse.quote(entity)
                        search_link = f"  → Search: https://www.google.com/search?q={search_query}"
                        formatted.append(clean_line)
                        formatted.append(search_link)
                    else:
                        formatted.append(clean_line)
                else:
                    formatted.append(clean_line)
                formatted.append("")  # Extra space
            formatted.append("")

        # 7. FOUNDER/ROLE-SPECIFIC INSIGHTS
        for section_name in content_sections:
            if 'Insights' in section_name and section_name not in ['Main Takeaways']:
                formatted.append(f"🚀 {section_name.upper()}")
                formatted.append("-" * 40)
                for line in content_sections[section_name]:
                    clean_line = line.replace('**', '').replace('*', '').replace('•', '-')
                    formatted.append(clean_line)
                    formatted.append("")
                formatted.append("")

        # 8. CRITICAL RATING (At bottom for context)
        if 'Critical Analysis & Rating' in content_sections:
            formatted.append("📊 CRITICAL ANALYSIS & RATING")
            formatted.append("-" * 40)
            for line in content_sections['Critical Analysis & Rating']:
                clean_line = line.replace('**', '').replace('*', '').replace('•', '-')
                formatted.append(clean_line)
            formatted.append("")

        # 9. EPISODE SUMMARY (Full context at end)
        if 'Episode Summary' in content_sections:
            formatted.append("📝 FULL EPISODE SUMMARY")
            formatted.append("-" * 40)
            for line in content_sections['Episode Summary']:
                clean_line = line.replace('**', '').replace('*', '')
                formatted.append(clean_line)
            formatted.append("")

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

            print(f"✓ Summary emailed to {self.email_config['email_to']}")
            return True

        except Exception as e:
            print(f"Error: Failed to send email - {e}")
            return False

    def process_url(self, url: str) -> Dict[str, any]:
        """Process a podcast URL"""
        print(f"\nProcessing: {url}")

        # Generate consistent ID
        podcast_id = self.generate_id(url)
        # Podcast ID: {podcast_id}

        # Check existing files
        existing = self.get_existing_files(podcast_id)

        # Get transcript (from cache, platform, or transcription)
        transcript = None

        if existing['transcript']:
            print(f"✓ Using cached transcript")
            transcript = existing['transcript'].read_text(encoding='utf-8')
        else:
            # Try to fetch platform transcript
            transcript = self.fetch_transcript(url)

            if transcript:
                print(f"✓ Found platform transcript")
                # Save fetched transcript
                transcript_path = self.transcript_dir / f"{podcast_id}.txt"
                transcript_path.write_text(transcript, encoding='utf-8')
            else:
                # Download and transcribe
                audio_path = existing['audio']

                if not audio_path:
                    print("Downloading audio...")
                    audio_path = self.download_audio(url, podcast_id)

                if audio_path:
                    transcript = self.transcribe_audio(audio_path, podcast_id)

        if not transcript:
            print("Error: Failed to obtain transcript")
            return {'success': False, 'error': 'Could not obtain transcript'}

        # Generate or use existing summary (check cache unless force regenerate)
        if existing['summary'] and not self.force_regenerate:
            print(f"✓ Using cached summary")
            summary = existing['summary'].read_text(encoding='utf-8')
        else:
            summary = self.summarize_transcript(transcript, podcast_id, url)

        # Send email if configured
        if self.enable_email and self.email_config:
            transcript_file = self.transcript_dir / f"{podcast_id}.txt"
            # Extract core insight for subject line
            metadata = self.extract_summary_metadata(summary)
            if metadata['core_insight']:
                # Truncate insight to 50 chars for subject
                insight_preview = metadata['core_insight'][:50] + "..." if len(metadata['core_insight']) > 50 else metadata['core_insight']
                subject = f"🎙️ {insight_preview}"
            else:
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

    def process_transcript(self, transcript_path: Path) -> Dict[str, any]:
        """Process an existing transcript file"""
        print(f"\nProcessing transcript: {transcript_path.name}")

        # Generate ID from filename
        podcast_id = transcript_path.stem

        # Read transcript
        if not transcript_path.exists():
            return {'success': False, 'error': f'Transcript file not found: {transcript_path}'}

        transcript = transcript_path.read_text(encoding='utf-8')

        # Check for existing summary (unless force regenerate)
        existing = self.get_existing_files(podcast_id)
        if existing['summary'] and not self.force_regenerate:
            print(f"✓ Using cached summary")
            summary = existing['summary'].read_text(encoding='utf-8')
        else:
            # Summarize
            summary = self.summarize_transcript(transcript, podcast_id, str(transcript_path))

        # Send email if configured
        if self.enable_email and self.email_config:
            # Extract core insight for subject line
            metadata = self.extract_summary_metadata(summary)
            if metadata['core_insight']:
                # Truncate insight to 50 chars for subject
                insight_preview = metadata['core_insight'][:50] + "..." if len(metadata['core_insight']) > 50 else metadata['core_insight']
                subject = f"🎙️ {insight_preview}"
            else:
                subject = f"Podcast Summary - {transcript_path.name}"
            self.send_email(subject, summary, str(transcript_path), transcript_path)

        return {
            'success': True,
            'id': podcast_id,
            'transcript_file': transcript_path,
            'summary_file': self.summary_dir / f"{podcast_id}.md",
            'summary': summary,
            'email_sent': self.email_config is not None
        }

    def process_mp3(self, mp3_path: Path) -> Dict[str, any]:
        """Process an existing MP3 file"""
        print(f"\nProcessing MP3: {mp3_path.name}")

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
            # Extract core insight for subject line
            metadata = self.extract_summary_metadata(summary)
            if metadata['core_insight']:
                # Truncate insight to 50 chars for subject
                insight_preview = metadata['core_insight'][:50] + "..." if len(metadata['core_insight']) > 50 else metadata['core_insight']
                subject = f"🎙️ {insight_preview}"
            else:
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
  %(prog)s --transcript transcript.txt
  %(prog)s --batch audio_files/*.mp3
        """
    )

    parser.add_argument('url', nargs='?', help='Podcast URL to process')
    parser.add_argument('--mp3', help='Process existing MP3 file')
    parser.add_argument('--transcript', help='Process existing transcript file')
    parser.add_argument('--batch', nargs='+', help='Process multiple files')
    parser.add_argument('--force', '-f', action='store_true', help='Force regeneration (skip cached summaries)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser.add_argument('--no-email', action='store_true', help='Disable email sending')
    parser.add_argument('--model', help='Claude model to use (opus, sonnet, haiku) - requires API access')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize processor
    processor = PodcastProcessor(
        enable_email=not args.no_email,
        force_regenerate=args.force,
        model=args.model
    )

    # Process based on input
    if args.batch:
        # Batch processing
        for file_pattern in args.batch:
            for file_path in Path().glob(file_pattern):
                if file_path.suffix.lower() in ['.mp3', '.m4a', '.wav']:
                    result = processor.process_mp3(file_path)
                    if result['success']:
                        # Extract and display metadata for batch processing
                        metadata = processor.extract_summary_metadata(result['summary'])
                        print(f"\n{'='*60}")
                        print(f"✅ Processed: {file_path.name}")
                        if metadata['podcast_name']:
                            print(f"   🎙️ {metadata['podcast_name']}")
                        if metadata['title']:
                            # Truncate long titles
                            title = metadata['title'][:50] + '...' if len(metadata['title']) > 50 else metadata['title']
                            print(f"   📝 {title}")
                        print(f"   📁 {result['summary_file'].name}")

    elif args.transcript:
        # Single transcript file
        transcript_path = Path(args.transcript)
        if not transcript_path.exists():
            print(f"Error: File not found - {args.transcript}")
            sys.exit(1)

        result = processor.process_transcript(transcript_path)
        if result['success']:
            # Extract and display metadata
            metadata = processor.extract_summary_metadata(result['summary'])
            print(f"\n{'='*60}")
            if metadata['podcast_name']:
                print(f"🎙️  Podcast: {metadata['podcast_name']}")
            if metadata['title']:
                print(f"📝  Episode: {metadata['title']}")
            if metadata['episode_info']:
                print(f"👤  Guest: {metadata['episode_info']}")
            if metadata['core_insight']:
                print(f"\n💡  Core Insight:\n    {metadata['core_insight']}")
            if metadata['useful_because']:
                print(f"\n✅  Useful Because:\n    {metadata['useful_because']}")
            print(f"{'='*60}\n")
            print(f"✓ Files saved:")
            print(f"  • Summary: {result['summary_file'].name}")
            if result.get('email_sent'):
                print(f"  • Email sent to {processor.email_config['email_to']}")

    elif args.mp3:
        # Single MP3
        mp3_path = Path(args.mp3)
        if not mp3_path.exists():
            print(f"Error: File not found - {args.mp3}")
            sys.exit(1)

        result = processor.process_mp3(mp3_path)
        if result['success']:
            # Extract and display metadata
            metadata = processor.extract_summary_metadata(result['summary'])
            print(f"\n{'='*60}")
            if metadata['podcast_name']:
                print(f"🎙️  Podcast: {metadata['podcast_name']}")
            if metadata['title']:
                print(f"📝  Episode: {metadata['title']}")
            if metadata['episode_info']:
                print(f"👤  Guest: {metadata['episode_info']}")
            if metadata['core_insight']:
                print(f"\n💡  Core Insight:\n    {metadata['core_insight']}")
            if metadata['useful_because']:
                print(f"\n✅  Useful Because:\n    {metadata['useful_because']}")
            print(f"{'='*60}\n")
            print(f"✓ Files saved:")
            print(f"  • Transcript: {result['transcript_file'].name}")
            print(f"  • Summary: {result['summary_file'].name}")
            if result.get('email_sent'):
                print(f"  • Email sent to {processor.email_config['email_to']}")

    elif args.url:
        # URL processing
        result = processor.process_url(args.url)
        if result['success']:
            # Extract and display metadata
            metadata = processor.extract_summary_metadata(result['summary'])
            print(f"\n{'='*60}")
            if metadata['podcast_name']:
                print(f"🎙️  Podcast: {metadata['podcast_name']}")
            if metadata['title']:
                print(f"📝  Episode: {metadata['title']}")
            if metadata['episode_info']:
                print(f"👤  Guest: {metadata['episode_info']}")
            if metadata['core_insight']:
                print(f"\n💡  Core Insight:\n    {metadata['core_insight']}")
            if metadata['useful_because']:
                print(f"\n✅  Useful Because:\n    {metadata['useful_because']}")
            print(f"{'='*60}\n")
            print(f"✓ Files saved:")
            print(f"  • Transcript: {result['transcript_file'].name}")
            print(f"  • Summary: {result['summary_file'].name}")
            if result.get('email_sent'):
                print(f"  • Email sent to {processor.email_config['email_to']}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()