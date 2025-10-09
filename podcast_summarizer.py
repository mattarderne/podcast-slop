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

    def __init__(self, base_dir: Path = None, enable_email: bool = True, force_regenerate: bool = False, model: str = None, custom_prompt: str = None):
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
        self.custom_prompt = custom_prompt

        # Load unified configuration
        self.config = self.load_unified_config()

        # Create directories
        for directory in [self.audio_dir, self.transcript_dir, self.summary_dir]:
            directory.mkdir(exist_ok=True)

        # Print output directories for easy access
        print(f"📁 Output directories:")
        print(f"   Transcripts: {self.transcript_dir.absolute()}")
        print(f"   Summaries:   {self.summary_dir.absolute()}")
        print(f"   Audio:       {self.audio_dir.absolute()}")

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
                    api = YouTubeTranscriptApi()
                    transcript_data = api.fetch(video_id)
                    return ' '.join([seg.text for seg in transcript_data])
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

        # Add custom prompt if provided
        if self.custom_prompt:
            prompt += f"\n\n## SPECIFIC REQUESTS:\n{self.custom_prompt}"

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

                # Validate summary completeness (should have key sections)
                required_sections = ['PODCAST_NAME:', 'TITLE:', 'Key Points', 'Episode Summary']
                missing_sections = [s for s in required_sections if s not in initial_summary]
                if missing_sections:
                    print(f"Warning: Summary appears incomplete (missing: {', '.join(missing_sections)})")
                    print(f"Summary length: {len(initial_summary)} chars")
                    if len(initial_summary) < 1000:
                        print(f"Error: Summary too short - Claude may have failed")
                        print(f"Output: {initial_summary[:200]}...")
                        return "Summary generation failed - output too short"

                # Second stage: Synthesize the core insight
                synthesis_template = self.get_default_prompts()['synthesis_prompt']

                # Replace placeholders in synthesis prompt
                synthesis_prompt = synthesis_template.replace('{user_context}', user_context)
                synthesis_prompt = synthesis_prompt.replace('{user_role}', user_role)
                synthesis_prompt = synthesis_prompt.replace('{user_interests}', user_interests)
                synthesis_prompt = synthesis_prompt.replace('{user_goals}', user_goals)
                synthesis_prompt = synthesis_prompt.replace('{summary}', initial_summary)

                # Add custom prompt to synthesis if provided
                if self.custom_prompt:
                    synthesis_prompt += f"\n\n## SPECIFIC REQUESTS:\n{self.custom_prompt}"

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

    def summarize_article(self, article_text: str, article_id: str, url: str) -> str:
        """Generate article summary using Claude with article-specific prompts"""
        summary_path = self.summary_dir / f"{article_id}.md"

        # Check if summary already exists (unless force regenerate)
        if summary_path.exists() and not self.force_regenerate:
            print(f"✓ Using cached summary")
            return summary_path.read_text(encoding='utf-8')

        # Get article-specific prompt template
        article_prompt_template = """You are analyzing written content for a {user_role}.

User Context: {user_context}
User Interests: {user_interests}
User Goals: {user_goals}

Please analyze the following article/text and provide a comprehensive summary:

## ARTICLE CONTENT:
{article_text}

## ANALYSIS FORMAT:

### ARTICLE_TITLE:
[Extract or infer the article title]

### SOURCE:
[Publication/website name if identifiable]

### KEY_ARGUMENTS:
• [Main thesis or central argument]
• [Supporting argument 1 with evidence]
• [Supporting argument 2 with evidence]
• [Additional key points with specifics]

### NOTABLE_INSIGHTS:
• [Unique perspective or finding 1]
• [Unique perspective or finding 2]
• [Additional insights that stand out]

### DATA_AND_EVIDENCE:
• [Key statistics, research findings, or case studies mentioned]
• [Metrics or quantitative evidence]
• [Examples or case studies cited]

### ACTIONABLE_TAKEAWAYS:
[Based on the user's role as {user_role}]
• [Specific action item 1]
• [Specific action item 2]
• [Additional practical applications]

### QUOTES_AND_EXCERPTS:
[5-7 most impactful quotes or passages from the text]
• "[Quote 1]"
• "[Quote 2]"
[Continue with memorable passages]

### CONTEXT_AND_BACKGROUND:
[Relevant context about the topic, author, or publication that helps understand the piece]

### CRITICAL_ANALYSIS:
[Potential weaknesses, biases, or counterarguments to consider]

### CONNECTIONS:
[How this relates to current trends, other ideas, or the user's interests]

### MAIN_SUMMARY:
[2-3 paragraph comprehensive summary capturing the essence and narrative of the article]

### USEFULNESS_RATING:
- Relevance: [1-10] - How relevant to {user_role}'s interests
- Depth: [1-10] - How thorough and well-researched
- Actionability: [1-10] - How practical and implementable
- Novelty: [1-10] - How new or unique the insights

### TOPICS:
#topic1 #topic2 #topic3 [relevant hashtags]"""

        # Prepare context variables from unified config
        profile = self.config.get('profile', {})
        user_context = profile.get('context', '')
        user_role = profile.get('role', 'general')
        user_interests = ', '.join(profile.get('interests', []))
        user_goals = '; '.join(profile.get('goals', []))

        # Replace placeholders in prompt template
        prompt = article_prompt_template.replace('{user_context}', user_context)
        prompt = prompt.replace('{user_role}', user_role)
        prompt = prompt.replace('{user_interests}', user_interests)
        prompt = prompt.replace('{user_goals}', user_goals)
        prompt = prompt.replace('{article_text}', article_text[:50000])

        # Add custom prompt if provided
        if self.custom_prompt:
            prompt += f"\n\n## SPECIFIC REQUESTS:\n{self.custom_prompt}"

        try:
            print("Generating article analysis...")
            result = subprocess.run(
                [str(self.claude_path), '--print', prompt],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes for comprehensive summaries
            )

            if result.returncode == 0 and result.stdout:
                initial_summary = result.stdout.strip()

                # Validate article analysis completeness
                required_sections = ['ARTICLE_TITLE:', 'KEY_ARGUMENTS:', 'MAIN_SUMMARY:']
                missing_sections = [s for s in required_sections if s not in initial_summary]
                if missing_sections:
                    print(f"Warning: Article analysis appears incomplete (missing: {', '.join(missing_sections)})")
                    print(f"Analysis length: {len(initial_summary)} chars")
                    if len(initial_summary) < 1000:
                        print(f"Error: Analysis too short - Claude may have failed")
                        print(f"Output: {initial_summary[:200]}...")
                        return "Article analysis failed - output too short"

                # Second stage: Synthesize the core insight for articles
                article_synthesis_template = """Based on this article analysis for a {user_role}:

{summary}

User Context: {user_context}
User Goals: {user_goals}

Please provide:

CORE_INSIGHT:
[The single most valuable insight or argument from this article - be specific and concrete]

USEFUL_BECAUSE:
[Explain in 2-3 sentences why this insight matters specifically for someone who is {user_context}. Focus on practical application and immediate value.]"""

                # Replace placeholders in synthesis prompt
                synthesis_prompt = article_synthesis_template.replace('{user_context}', user_context)
                synthesis_prompt = synthesis_prompt.replace('{user_role}', user_role)
                synthesis_prompt = synthesis_prompt.replace('{user_goals}', user_goals)
                synthesis_prompt = synthesis_prompt.replace('{summary}', initial_summary)

                # Add custom prompt to synthesis if provided
                if self.custom_prompt:
                    synthesis_prompt += f"\n\n## SPECIFIC REQUESTS:\n{self.custom_prompt}"

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
ID: {article_id}
URL: {url}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Type: Article
---

"""
                full_summary = header + synthesis + initial_summary

                # Save summary with synthesis
                summary_path.write_text(full_summary, encoding='utf-8')
                print(f"✓ Article analysis generated with core insight")

                return full_summary
            else:
                print(f"Error: Claude failed - {result.stderr}")
                return "Article analysis failed"

        except subprocess.TimeoutExpired:
            print("Error: Claude analysis timed out (5 minute limit)")
            return "Article analysis timed out"
        except Exception as e:
            print(f"Error: Analysis failed - {e}")
            return f"Article analysis failed: {e}"

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
        capture_field = None
        field_lines = []

        for line in lines:
            # Check if we're starting a new field (handle both with and without ##)
            if line.startswith('PODCAST_NAME:') or line.startswith('## PODCAST_NAME:'):
                metadata['podcast_name'] = line.replace('## ', '').replace('PODCAST_NAME:', '').strip()
                capture_field = None
            elif line.startswith('TITLE:') or line.startswith('## TITLE:'):
                metadata['title'] = line.replace('## ', '').replace('TITLE:', '').strip()
                capture_field = None
            elif line.startswith('EPISODE_INFO:') or line.startswith('## EPISODE_INFO:'):
                metadata['episode_info'] = line.replace('## ', '').replace('EPISODE_INFO:', '').strip()
                capture_field = None
            elif line.startswith('CORE_INSIGHT:') or line.startswith('## CORE_INSIGHT:'):
                text = line.replace('## ', '').replace('CORE_INSIGHT:', '').strip()
                if text:
                    metadata['core_insight'] = text
                    capture_field = None
                else:
                    capture_field = 'core_insight'
                    field_lines = []
            elif line.startswith('USEFUL_BECAUSE:') or line.startswith('## USEFUL_BECAUSE:'):
                text = line.replace('## ', '').replace('USEFUL_BECAUSE:', '').strip()
                if text:
                    metadata['useful_because'] = text
                    capture_field = None
                else:
                    capture_field = 'useful_because'
                    field_lines = []
            # Capture multi-line content
            elif capture_field and line.strip() and not line.startswith('#') and not line.startswith('---'):
                field_lines.append(line.strip())
            elif capture_field and (not line.strip() or line.startswith('#') or line.startswith('---')):
                # End of multi-line content
                if field_lines:
                    metadata[capture_field] = ' '.join(field_lines)
                capture_field = None
                field_lines = []

        # Handle any remaining captured field
        if capture_field and field_lines:
            metadata[capture_field] = ' '.join(field_lines)

        return metadata

    def format_email_body(self, summary: str, url: str = None) -> str:
        """Format summary for plain text email (Gmail-friendly with better spacing)"""
        import urllib.parse
        lines = summary.split('\n')
        formatted = []

        # Extract metadata using the proper extraction method
        metadata = self.extract_summary_metadata(summary)

        # Extract content sections
        content_sections = {}
        current_section = None
        section_content = []

        for line in lines:
            # Capture sections (both ## for podcasts and ### for articles)
            if line.startswith('## ') or line.startswith('### '):
                if current_section and section_content:
                    content_sections[current_section] = section_content
                current_section = line.replace('### ', '').replace('## ', '').strip().rstrip(':')
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
        if metadata.get('title'):
            formatted.append(f"EPISODE: {metadata['title']}")
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

        # Check if it's an article based on sections present
        is_article = 'KEY_ARGUMENTS' in content_sections or 'ACTIONABLE_TAKEAWAYS' in content_sections

        if is_article:
            # Article-specific formatting

            # 3. ACTIONABLE TAKEAWAYS
            if 'ACTIONABLE_TAKEAWAYS' in content_sections:
                formatted.append("🎯 ACTIONABLE TAKEAWAYS")
                formatted.append("-" * 40)
                for line in content_sections['ACTIONABLE_TAKEAWAYS']:
                    clean_line = line.replace('**', '').replace('*', '').replace('•', '-')
                    formatted.append(clean_line)
                    formatted.append("")  # Extra space between items
                formatted.append("")

            # 4. KEY ARGUMENTS
            if 'KEY_ARGUMENTS' in content_sections:
                formatted.append("📌 KEY ARGUMENTS")
                formatted.append("-" * 40)
                for line in content_sections['KEY_ARGUMENTS']:
                    clean_line = line.replace('**', '').replace('*', '').replace('•', '-')
                    formatted.append(clean_line)
                    formatted.append("")
                formatted.append("")

            # 5. DATA & EVIDENCE
            if 'DATA_AND_EVIDENCE' in content_sections:
                formatted.append("📊 DATA & EVIDENCE")
                formatted.append("-" * 40)
                for line in content_sections['DATA_AND_EVIDENCE']:
                    clean_line = line.replace('**', '').replace('*', '').replace('•', '-')
                    formatted.append(clean_line)
                    formatted.append("")
                formatted.append("")

            # 6. NOTABLE INSIGHTS
            if 'NOTABLE_INSIGHTS' in content_sections:
                formatted.append("💡 NOTABLE INSIGHTS")
                formatted.append("-" * 40)
                for line in content_sections['NOTABLE_INSIGHTS']:
                    clean_line = line.replace('**', '').replace('*', '').replace('•', '-')
                    formatted.append(clean_line)
                    formatted.append("")
                formatted.append("")

            # 7. QUOTES
            if 'QUOTES_AND_EXCERPTS' in content_sections:
                formatted.append("💬 KEY QUOTES")
                formatted.append("-" * 40)
                for line in content_sections['QUOTES_AND_EXCERPTS']:
                    clean_line = line.replace('**', '').replace('*', '').replace('•', '"')
                    formatted.append(clean_line)
                    formatted.append("")
                formatted.append("")

            # 8. CUSTOM SECTIONS (Handle any LinkedIn, Twitter, or other custom sections)
            for section_name in content_sections:
                if 'LINKEDIN' in section_name.upper() or 'TWITTER' in section_name.upper() or 'QUOTES FOR' in section_name.upper():
                    if section_name not in ['QUOTES_AND_EXCERPTS', 'NOTABLE_INSIGHTS', 'KEY_ARGUMENTS',
                                           'DATA_AND_EVIDENCE', 'ACTIONABLE_TAKEAWAYS', 'MAIN_SUMMARY']:
                        formatted.append("🚀 CUSTOM CONTENT")
                        formatted.append("-" * 40)
                        for line in content_sections[section_name]:
                            clean_line = line.replace('**', '').replace('*', '')
                            formatted.append(clean_line)
                            formatted.append("")
                        formatted.append("")
                        break  # Only include first custom section to avoid duplicates

        else:
            # Podcast-specific formatting (existing code)

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

        # 9. EPISODE/ARTICLE SUMMARY (Full context at end)
        if 'Episode Summary' in content_sections:
            formatted.append("📝 FULL EPISODE SUMMARY")
            formatted.append("-" * 40)
            for line in content_sections['Episode Summary']:
                clean_line = line.replace('**', '').replace('*', '')
                formatted.append(clean_line)
            formatted.append("")
        elif 'MAIN_SUMMARY' in content_sections:
            formatted.append("📝 FULL ARTICLE SUMMARY")
            formatted.append("-" * 40)
            for line in content_sections['MAIN_SUMMARY']:
                clean_line = line.replace('**', '').replace('*', '')
                formatted.append(clean_line)
            formatted.append("")

        return '\n'.join(formatted)

    def generate_pdf(self, summary_path: Path, frames_dir: Path = None) -> Optional[Path]:
        """Generate PDF from markdown summary with optional screenshots"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
            from reportlab.lib.enums import TA_LEFT
            import re
        except ImportError:
            print("Installing PDF generation dependencies...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'reportlab'],
                         check=True, capture_output=True)
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
            from reportlab.lib.enums import TA_LEFT
            import re

        try:
            # Read markdown
            md_content = summary_path.read_text(encoding='utf-8')

            # Generate PDF
            pdf_path = summary_path.with_suffix('.pdf')
            doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
            story = []
            styles = getSampleStyleSheet()

            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=12,
            )
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=10,
            )
            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['BodyText'],
                fontSize=10,
                spaceAfter=6,
            )

            # Parse markdown content
            lines = md_content.split('\n')
            in_metadata = False

            for line in lines:
                line = line.strip()

                # Skip metadata
                if line == '---':
                    in_metadata = not in_metadata
                    continue
                if in_metadata:
                    continue

                if not line:
                    story.append(Spacer(1, 0.1 * inch))
                    continue

                # Headers
                if line.startswith('### '):
                    story.append(Paragraph(line[4:], heading_style))
                elif line.startswith('## '):
                    story.append(Paragraph(line[3:], heading_style))
                elif line.startswith('# '):
                    story.append(Paragraph(line[2:], title_style))
                # Lists
                elif line.startswith('• ') or line.startswith('- '):
                    story.append(Paragraph(f"&bull; {line[2:]}", body_style))
                # Regular text
                else:
                    story.append(Paragraph(line, body_style))

            # Add screenshots if available
            if frames_dir and frames_dir.exists():
                frames = sorted(list(frames_dir.glob("frame_*.jpg")))[:10]
                if frames:
                    story.append(PageBreak())
                    story.append(Paragraph("Screenshots", heading_style))
                    story.append(Spacer(1, 0.2 * inch))

                    for frame_path in frames:
                        try:
                            img = Image(str(frame_path), width=5*inch, height=3*inch)
                            story.append(img)
                            story.append(Paragraph(frame_path.stem, body_style))
                            story.append(Spacer(1, 0.2 * inch))
                        except:
                            pass  # Skip problematic images

            doc.build(story)
            print(f"✓ PDF generated")
            return pdf_path

        except Exception as e:
            print(f"Warning: PDF generation failed - {e}")
            return None

    def send_email(self, subject: str, body: str, url: str = None, summary_path: Path = None, frames_dir: Path = None) -> bool:
        """Send email with summary and PDF attachment (with screenshots if available)"""
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

            # Generate and attach PDF (with screenshots if available)
            if summary_path and summary_path.exists():
                pdf_path = self.generate_pdf(summary_path, frames_dir)
                if pdf_path and pdf_path.exists():
                    with open(pdf_path, 'rb') as f:
                        part = MIMEBase('application', 'pdf')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename="{pdf_path.name}"'
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

    def detect_content_type(self, input_path: str) -> str:
        """Detect what type of content this is"""
        # Check if it's a local file
        local_path = Path(input_path)
        if local_path.exists() and local_path.is_file():
            ext = local_path.suffix.lower()
            if ext in ['.mp3', '.m4a', '.wav', '.aac', '.flac']:
                return 'audio'
            elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
                return 'video'
            elif ext in ['.txt', '.md']:
                return 'transcript'
            else:
                return 'unknown'

        # It's a URL - check patterns
        url_lower = input_path.lower()

        # Video platforms
        if any(x in url_lower for x in ['youtube.com', 'youtu.be', 'vimeo.com']):
            return 'video'

        # Known podcast platforms
        if any(x in url_lower for x in ['pca.st', 'pocketcasts.com', 'spotify.com/episode']):
            return 'podcast'

        # Check if it's a direct media file URL
        if any(url_lower.endswith(x) for x in ['.mp3', '.m4a', '.wav']):
            return 'podcast'

        # For other URLs, try to detect if it's an article by fetching headers
        try:
            response = requests.head(input_path, timeout=5, allow_redirects=True)
            content_type = response.headers.get('content-type', '').lower()

            if 'audio' in content_type:
                return 'podcast'
            elif 'video' in content_type:
                return 'video'
            elif any(x in content_type for x in ['text/html', 'application/xhtml']):
                return 'article'
        except:
            pass

        # Default to article for unknown URLs (safer than failing)
        return 'article'

    def smart_process(self, input_path: str, force_type: str = None) -> Dict[str, any]:
        """Intelligently process any input based on detected type"""
        # Detect type unless forced
        content_type = force_type if force_type else self.detect_content_type(input_path)

        print(f"Detected content type: {content_type}")

        # Route to appropriate processor
        if content_type == 'audio':
            return self.process_mp3(Path(input_path))
        elif content_type == 'video':
            # Check if it's a local file
            local_path = Path(input_path)
            if local_path.exists():
                return self.process_local_video(local_path)
            else:
                return self.process_url_video(input_path)
        elif content_type == 'transcript':
            return self.process_transcript(Path(input_path))
        elif content_type == 'article':
            return self.process_article(input_path)
        elif content_type == 'podcast':
            return self.process_url(input_path)
        else:
            return {'success': False, 'error': f'Unknown content type: {content_type}'}

    def process_local_video(self, video_path: Path) -> Dict[str, any]:
        """Process local video file - extract audio and transcribe"""
        print(f"\nProcessing local video: {video_path.name}")

        # Generate ID from filename
        video_id = video_path.stem

        # Extract audio to MP3
        audio_path = self.audio_dir / f"{video_id}.mp3"

        if not audio_path.exists():
            print("Extracting audio from video...")
            try:
                import subprocess
                # Use ffmpeg to extract audio
                subprocess.run([
                    'ffmpeg', '-i', str(video_path),
                    '-vn', '-acodec', 'libmp3lame',
                    '-q:a', '2', str(audio_path)
                ], check=True, capture_output=True)
                print("✓ Audio extracted")
            except Exception as e:
                print(f"Error: Audio extraction failed - {e}")
                return {'success': False, 'error': 'Audio extraction failed'}

        # Now process as audio
        return self.process_mp3(audio_path)

    def process_url_video(self, url: str) -> Dict[str, any]:
        """Process video URL - download, transcribe, and summarize"""
        print(f"\nProcessing video: {url}")

        # Generate ID
        video_id = self.generate_id(url)

        # Check existing files
        existing = self.get_existing_files(video_id)

        # Get transcript
        transcript = None

        if existing['transcript']:
            print(f"✓ Using cached transcript")
            transcript = existing['transcript'].read_text(encoding='utf-8')
        else:
            # Try to fetch platform transcript first (YouTube)
            transcript = self.fetch_transcript(url)

            if transcript:
                print(f"✓ Found platform transcript")
                transcript_path = self.transcript_dir / f"{video_id}.txt"
                transcript_path.write_text(transcript, encoding='utf-8')
            else:
                # Download audio and transcribe
                audio_path = existing['audio']

                if not audio_path:
                    print("Downloading audio from video...")
                    audio_path = self.download_audio(url, video_id)

                if audio_path:
                    transcript = self.transcribe_audio(audio_path, video_id)

        if not transcript:
            print("Error: Failed to obtain transcript")
            return {'success': False, 'error': 'Could not obtain transcript'}

        # Generate summary
        if existing['summary'] and not self.force_regenerate:
            print(f"✓ Using cached summary")
            summary = existing['summary'].read_text(encoding='utf-8')
        else:
            summary = self.summarize_transcript(transcript, video_id, url)

        # Generate PDF
        summary_file = self.summary_dir / f"{video_id}.md"
        pdf_path = self.generate_pdf(summary_file)

        # Send email if configured
        if self.enable_email and self.email_config:
            metadata = self.extract_summary_metadata(summary)
            if metadata['core_insight']:
                insight_preview = metadata['core_insight'][:50] + "..." if len(metadata['core_insight']) > 50 else metadata['core_insight']
                subject = f"🎬 {insight_preview}"
            else:
                subject = f"Video Summary - {video_id}"
            self.send_email(subject, summary, url, summary_file)

        return {
            'success': True,
            'id': video_id,
            'url': url,
            'transcript_file': self.transcript_dir / f"{video_id}.txt",
            'summary_file': self.summary_dir / f"{video_id}.md",
            'summary': summary,
            'email_sent': self.email_config is not None
        }

    def process_url(self, url: str) -> Dict[str, any]:
        """Process a podcast URL"""
        print(f"\nProcessing podcast: {url}")

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

        # Always generate PDF
        summary_file = self.summary_dir / f"{podcast_id}.md"
        pdf_path = self.generate_pdf(summary_file)

        # Send email if configured
        if self.enable_email and self.email_config:
            # Extract core insight for subject line
            metadata = self.extract_summary_metadata(summary)
            if metadata['core_insight']:
                # Truncate insight to 50 chars for subject
                insight_preview = metadata['core_insight'][:50] + "..." if len(metadata['core_insight']) > 50 else metadata['core_insight']
                subject = f"🎙️ {insight_preview}"
            else:
                subject = f"Podcast Summary - {podcast_id}"
            self.send_email(subject, summary, url, summary_file)

        return {
            'success': True,
            'id': podcast_id,
            'url': url,
            'transcript_file': self.transcript_dir / f"{podcast_id}.txt",
            'summary_file': self.summary_dir / f"{podcast_id}.md",
            'summary': summary,
            'email_sent': self.email_config is not None
        }

    def process_article(self, url: str) -> Dict[str, any]:
        """Process an article/text URL"""
        print(f"\nProcessing article: {url}")

        # Generate ID from URL
        article_id = f"article_{self.generate_id(url)}"

        # Check for existing summary
        existing = self.get_existing_files(article_id)
        if existing['summary'] and not self.force_regenerate:
            print(f"✓ Using cached summary")
            summary = existing['summary'].read_text(encoding='utf-8')
        else:
            # Fetch and process the article
            print("Fetching article content...")
            article_text = self.fetch_article(url)

            if not article_text:
                return {'success': False, 'error': 'Could not fetch article content'}

            # Save article text as "transcript"
            transcript_path = self.transcript_dir / f"{article_id}.txt"
            transcript_path.write_text(article_text, encoding='utf-8')

            # Generate summary with article-specific prompt
            summary = self.summarize_article(article_text, article_id, url)

        # Always generate PDF
        summary_file = self.summary_dir / f"{article_id}.md"
        pdf_path = self.generate_pdf(summary_file)

        # Send email if configured
        if self.enable_email and self.email_config:
            metadata = self.extract_summary_metadata(summary)
            if metadata['core_insight']:
                insight_preview = metadata['core_insight'][:50] + "..." if len(metadata['core_insight']) > 50 else metadata['core_insight']
                subject = f"📄 {insight_preview}"
            else:
                subject = f"Article Summary - {article_id}"
            self.send_email(subject, summary, url, summary_file)

        return {
            'success': True,
            'id': article_id,
            'url': url,
            'transcript_file': self.transcript_dir / f"{article_id}.txt",
            'summary_file': self.summary_dir / f"{article_id}.md",
            'summary': summary,
            'email_sent': self.email_config is not None
        }

    def fetch_article(self, url: str) -> Optional[str]:
        """Fetch article content using WebFetch approach"""
        try:
            # Use requests to fetch HTML
            response = requests.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            response.raise_for_status()

            # Convert HTML to text (basic extraction)
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text = []
                    self.skip_tags = {'script', 'style', 'meta', 'link'}
                    self.current_tag = None

                def handle_starttag(self, tag, attrs):
                    self.current_tag = tag

                def handle_endtag(self, tag):
                    self.current_tag = None

                def handle_data(self, data):
                    if self.current_tag not in self.skip_tags:
                        text = data.strip()
                        if text:
                            self.text.append(text)

            parser = TextExtractor()
            parser.feed(response.text)

            article_text = '\n'.join(parser.text)

            # Basic cleanup
            lines = article_text.split('\n')
            cleaned = []
            for line in lines:
                if len(line) > 30:  # Filter out short lines (likely navigation)
                    cleaned.append(line)

            return '\n\n'.join(cleaned)

        except Exception as e:
            print(f"Error fetching article: {e}")
            return None

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

        # Always generate PDF
        summary_file = self.summary_dir / f"{podcast_id}.md"
        pdf_path = self.generate_pdf(summary_file)

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
            self.send_email(subject, summary, str(transcript_path), summary_file)

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

        # Always generate PDF
        summary_file = self.summary_dir / f"{podcast_id}.md"
        pdf_path = self.generate_pdf(summary_file)

        # Send email if configured
        if self.enable_email and self.email_config:
            # Extract core insight for subject line
            metadata = self.extract_summary_metadata(summary)
            if metadata['core_insight']:
                # Truncate insight to 50 chars for subject
                insight_preview = metadata['core_insight'][:50] + "..." if len(metadata['core_insight']) > 50 else metadata['core_insight']
                subject = f"🎙️ {insight_preview}"
            else:
                subject = f"Podcast Summary - {mp3_path.name}"
            self.send_email(subject, summary, str(mp3_path), summary_file)

        return {
            'success': True,
            'id': podcast_id,
            'mp3_file': mp3_path,
            'transcript_file': self.transcript_dir / f"{podcast_id}.txt",
            'summary_file': self.summary_dir / f"{podcast_id}.md",
            'summary': summary,
            'email_sent': self.email_config is not None
        }

    def extract_video_frames(self, video_path: Path, output_dir: Path, interval_seconds: int = 30) -> list:
        """Extract frames from video at regular intervals"""
        try:
            import cv2
        except ImportError:
            print("Installing opencv-python...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'opencv-python'], check=True, capture_output=True)
            import cv2

        output_dir.mkdir(exist_ok=True)
        frames = []

        try:
            video = cv2.VideoCapture(str(video_path))
            fps = video.get(cv2.CAP_PROP_FPS)
            frame_interval = int(fps * interval_seconds)
            frame_count = 0
            saved_count = 0

            while True:
                ret, frame = video.read()
                if not ret:
                    break

                if frame_count % frame_interval == 0:
                    frame_path = output_dir / f"frame_{saved_count:04d}.jpg"
                    cv2.imwrite(str(frame_path), frame)
                    frames.append(frame_path)
                    saved_count += 1

                frame_count += 1

            video.release()
            print(f"✓ Extracted {len(frames)} frames")
            return frames

        except Exception as e:
            print(f"Error extracting frames: {e}")
            return []

    def download_video(self, url: str, video_id: str) -> Optional[Path]:
        """Download video from URL"""
        output_path = self.audio_dir / f"{video_id}.mp4"

        try:
            import yt_dlp
        except ImportError:
            print("Installing yt-dlp...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'yt-dlp'], check=True, capture_output=True)
            import yt_dlp

        try:
            ydl_opts = {
                'format': 'best[height<=720]',  # Max 720p to save space
                'outtmpl': str(output_path),
                'quiet': True,
                'no_warnings': True,
                'noprogress': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # Get the actual filename after download
                downloaded_file = ydl.prepare_filename(info)
                output_path = Path(downloaded_file)

            if output_path.exists():
                print(f"✓ Video downloaded")
                return output_path
            else:
                print("Error: Video file not found after download")
                return None

        except Exception as e:
            print(f"Error: Video download failed - {e}")
            return None

    def summarize_video_screenshots(self, frames: list, video_id: str, url: str) -> str:
        """Generate summary based on video frames using Claude"""
        summary_path = self.summary_dir / f"{video_id}.md"

        # Check if summary already exists (unless force regenerate)
        if summary_path.exists() and not self.force_regenerate:
            print(f"✓ Using cached summary")
            return summary_path.read_text(encoding='utf-8')

        # Prepare prompt for visual analysis
        profile = self.config.get('profile', {})
        user_context = profile.get('context', '')
        user_role = profile.get('role', 'general')
        user_interests = ', '.join(profile.get('interests', []))
        user_goals = '; '.join(profile.get('goals', []))

        # Use Claude API via Python SDK for image support
        try:
            import anthropic
            import base64
        except ImportError:
            print("Installing anthropic SDK...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'anthropic'], check=True, capture_output=True)
            import anthropic
            import base64

        try:
            print("Analyzing video frames with Claude...")

            # Prepare image content for API
            content = []

            # Add text prompt
            prompt_text = f"""Analyze these video frames and create a comprehensive visual summary.

User Context: {user_context}
User Role: {user_role}
User Interests: {user_interests}
User Goals: {user_goals}

I'm providing {len(frames[:20])} frames extracted from a video at regular intervals (every 30 seconds). Please analyze them and provide:

## VIDEO_TITLE:
[Infer the video title/topic from visual content]

## VISUAL_CONTENT_SUMMARY:
Describe what's shown in the video based on the frames:
• Main topics or themes visible
• Key visual elements (slides, demonstrations, people, etc.)
• Any text visible in frames (titles, captions, key points)
• Progression or narrative arc visible across frames

## KEY_POINTS:
• Extract 5-10 main points visible from text in slides/captions
• Include any statistics, diagrams, or important visual information

## ACTIONABLE_INSIGHTS:
[Based on the user's role as {user_role}]
• Specific takeaways that appear actionable
• Frameworks or concepts shown visually

## VISUAL_HIGHLIGHTS:
• Notable slides, diagrams, or visual explanations
• Important timestamps (approximate based on frame sequence)

## OVERALL_ASSESSMENT:
[2-3 paragraphs synthesizing the video's content and value]

## USEFULNESS_RATING:
- Visual Quality: [1-10] - How clear and informative the visuals are
- Content Depth: [1-10] - How substantive the content appears
- Relevance: [1-10] - How relevant to {user_role}'s interests"""

            if self.custom_prompt:
                prompt_text += f"\n\n## SPECIFIC REQUESTS:\n{self.custom_prompt}"

            content.append({
                "type": "text",
                "text": prompt_text
            })

            # Add images (limit to 20 frames to avoid overwhelming)
            for i, frame_path in enumerate(frames[:20]):
                with open(frame_path, 'rb') as f:
                    image_data = base64.standard_b64encode(f.read()).decode('utf-8')
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_data
                        }
                    })

            # Load .env file to get API key
            env_file = self.script_dir / '.env'
            if env_file.exists():
                try:
                    from dotenv import load_dotenv
                    load_dotenv(env_file)
                except ImportError:
                    # Manual .env parsing
                    with open(env_file, 'r') as f:
                        for line in f:
                            if '=' in line and not line.strip().startswith('#'):
                                key, value = line.strip().split('=', 1)
                                os.environ[key] = value.strip('"').strip("'")

            # Get API key from environment
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                print("\nError: ANTHROPIC_API_KEY not found")
                print("To use screenshots mode, add your Anthropic API key to .env file:")
                print("  echo 'ANTHROPIC_API_KEY=your-key-here' >> .env")
                print("\nGet your API key at: https://console.anthropic.com/")
                return "Video analysis failed: Missing API key"

            # Call Claude API
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": content
                }]
            )

            analysis = message.content[0].text

            # Add metadata header
            header = f"""---
ID: {video_id}
URL: {url}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Type: Video (Screenshots)
Frames Analyzed: {len(frames[:20])}
---

"""
            full_summary = header + analysis

            # Save summary
            summary_path.write_text(full_summary, encoding='utf-8')
            print(f"✓ Video analysis generated from screenshots")

            return full_summary

        except Exception as e:
            print(f"Error: Analysis failed - {e}")
            return f"Video analysis failed: {e}"

    def get_strategic_timestamps(self, transcript: str, video_duration: float, max_frames: int = 20) -> list:
        """Use Claude to identify strategic timestamps from transcript"""
        try:
            print("Analyzing transcript for strategic moments...")

            prompt = f"""Analyze this video transcript and identify the {max_frames} most important moments that would benefit from visual screenshots.

Video duration: {video_duration:.0f} seconds

For each moment, provide:
1. Timestamp (in seconds)
2. Brief reason why this moment is visually important

Focus on moments where:
- Key concepts are being explained (likely with slides/diagrams)
- Important statistics or data are mentioned
- Product demos or visual examples are shown
- Transitions between major topics
- Critical insights or conclusions

Transcript:
{transcript[:30000]}

Provide your response as a JSON array of objects with "timestamp" (number in seconds) and "reason" (string) fields.
Example: [{{"timestamp": 45, "reason": "Introduction of main concept"}}, {{"timestamp": 120, "reason": "Key statistics presentation"}}]

Ensure timestamps are evenly distributed and cover the full video duration."""

            result = subprocess.run(
                [str(self.claude_path), '--print', prompt],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0 and result.stdout:
                # Parse JSON response
                import json
                try:
                    # Extract JSON from response (might have markdown code blocks)
                    response = result.stdout.strip()
                    if '```json' in response:
                        response = response.split('```json')[1].split('```')[0].strip()
                    elif '```' in response:
                        response = response.split('```')[1].split('```')[0].strip()

                    timestamps_data = json.loads(response)
                    timestamps = [t['timestamp'] for t in timestamps_data if 0 <= t['timestamp'] <= video_duration]
                    print(f"✓ Identified {len(timestamps)} strategic moments")
                    return timestamps
                except:
                    pass

        except Exception as e:
            print(f"Warning: Could not analyze transcript strategically - {e}")

        # Fallback to uniform intervals
        return None

    def extract_strategic_frames(self, video_path: Path, output_dir: Path, timestamps: list) -> list:
        """Extract frames at specific timestamps"""
        try:
            import cv2
        except ImportError:
            print("Installing opencv-python...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'opencv-python'], check=True, capture_output=True)
            import cv2

        output_dir.mkdir(exist_ok=True)
        frames = []

        try:
            video = cv2.VideoCapture(str(video_path))
            fps = video.get(cv2.CAP_PROP_FPS)

            for i, timestamp in enumerate(timestamps):
                # Seek to timestamp
                frame_number = int(timestamp * fps)
                video.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

                ret, frame = video.read()
                if ret:
                    frame_path = output_dir / f"frame_{i:04d}_t{int(timestamp)}s.jpg"
                    cv2.imwrite(str(frame_path), frame)
                    frames.append(frame_path)

            video.release()
            print(f"✓ Extracted {len(frames)} strategic frames")
            return frames

        except Exception as e:
            print(f"Error extracting frames: {e}")
            return []

    def process_video_screenshots(self, url: str, interval_seconds: int = 30) -> Dict[str, any]:
        """Process video by extracting and analyzing screenshots"""
        print(f"\nProcessing video (screenshots mode): {url}")

        # Check if input is a local file
        local_video_path = Path(url)
        is_local_file = local_video_path.exists() and local_video_path.is_file()

        # Generate ID
        if is_local_file:
            video_id = f"video_{local_video_path.stem}"
        else:
            video_id = f"video_{self.generate_id(url)}"

        frames_dir = self.base_dir / "video_frames" / video_id
        frames_dir.mkdir(parents=True, exist_ok=True)

        # Initialize frames list
        frames = []

        # Check for existing summary
        existing = self.get_existing_files(video_id)
        if existing['summary'] and not self.force_regenerate:
            print(f"✓ Using cached summary")
            summary = existing['summary'].read_text(encoding='utf-8')
            # Check if frames already exist
            if frames_dir.exists():
                frames = sorted(frames_dir.glob("frame_*.jpg"))
        else:
            # Get video path (local or download)
            if is_local_file:
                print(f"Using local video file: {local_video_path}")
                video_path = local_video_path
            else:
                # Download video
                print("Downloading video...")
                video_path = self.download_video(url, video_id)

            if not video_path:
                return {'success': False, 'error': 'Video download failed'}

            # Get video duration
            try:
                import cv2
                video = cv2.VideoCapture(str(video_path))
                fps = video.get(cv2.CAP_PROP_FPS)
                frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
                duration = frame_count / fps if fps > 0 else 0
                video.release()
            except:
                duration = 0

            # Extract 15 evenly spaced frames
            print(f"Extracting 15 evenly spaced frames...")
            frames = []
            if duration > 0:
                # Calculate timestamps for 15 evenly spaced frames
                num_frames = 15
                timestamps = [duration * i / (num_frames - 1) for i in range(num_frames)]
                frames = self.extract_strategic_frames(video_path, frames_dir, timestamps)
            else:
                # Fallback to interval-based extraction if duration unknown
                frames = self.extract_video_frames(video_path, frames_dir, interval_seconds)

            if not frames:
                return {'success': False, 'error': 'Frame extraction failed'}

            # Analyze frames
            summary = self.summarize_video_screenshots(frames, video_id, url)

        # Always generate PDF (with screenshots)
        summary_file = self.summary_dir / f"{video_id}.md"
        pdf_path = self.generate_pdf(summary_file, frames_dir if frames else None)

        # Send email if configured
        if self.enable_email and self.email_config:
            metadata = self.extract_summary_metadata(summary)
            if metadata.get('core_insight'):
                insight_preview = metadata['core_insight'][:50] + "..." if len(metadata['core_insight']) > 50 else metadata['core_insight']
                subject = f"🎬 {insight_preview}"
            else:
                subject = f"Video Summary - {video_id}"
            self.send_email(subject, summary, url, summary_file, frames_dir=frames_dir if frames else None)

        return {
            'success': True,
            'id': video_id,
            'url': url,
            'frames_dir': frames_dir,
            'summary_file': self.summary_dir / f"{video_id}.md",
            'summary': summary,
            'email_sent': self.email_config is not None
        }


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Automatically transcribe and summarize any content - podcasts, videos, articles, or local files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
SMART AUTO-DETECTION:
  The tool automatically detects what type of content you're processing:

  • URLs: Checks domain patterns and HTTP headers
    - youtube.com/youtu.be/vimeo.com → Video (transcribed)
    - pca.st/pocketcasts/spotify → Podcast (downloaded & transcribed)
    - Other URLs → Article (text extracted & analyzed)

  • Local files: Detects from file extension
    - .mp4/.avi/.mov/.mkv/.webm → Video (audio extracted & transcribed)
    - .mp3/.m4a/.wav/.aac/.flac → Audio (transcribed)
    - .txt/.md → Transcript (summarized directly)

EXAMPLES:
  # Just provide any input - auto-detection handles it!
  %(prog)s "https://youtube.com/watch?v=..."      # → Video
  %(prog)s "https://pca.st/episode/abc123"        # → Podcast
  %(prog)s "https://mckinsey.com/article"         # → Article
  %(prog)s video.mp4                              # → Local video
  %(prog)s audio.mp3                              # → Local audio
  %(prog)s transcript.txt                         # → Transcript

  # Batch processing (handles mixed types automatically)
  %(prog)s --batch media_files/*
  %(prog)s --batch *.mp4 *.mp3 *.txt              # Mixed formats!

  # Force specific processing mode (override auto-detection)
  %(prog)s -t "https://example.com"               # Force as article
  %(prog)s --screenshots "https://youtube.com"    # Screenshot analysis

  # Add custom instructions to any content type
  %(prog)s -p "extract 4 linkedin quotes" "url"
  %(prog)s -p "focus on statistics" "https://blog.example.com"

  # Other options
  %(prog)s --force "url"                          # Skip cache, regenerate
  %(prog)s --no-email "url"                       # Don't send email
  %(prog)s --verbose "url"                        # Show detailed logs

WHAT GETS SENT:
  • Personalized summary based on your podcast_config.yaml
  • PDF attachment with full summary
  • Core insights extracted and highlighted
  • Email subject with key takeaway

AUTO-DETECTION DETAILS:
  Local files → Extension (.mp4, .mp3, .txt, etc.)
  YouTube/Vimeo → Video mode (fetches captions if available)
  Podcast platforms → Audio download mode
  Other URLs → HTTP Content-Type header check
  Unknown → Defaults to article mode (safe fallback)
        """
    )

    parser.add_argument('url', nargs='?',
                       help='URL or file path to process (automatically detects type)')

    parser.add_argument('--batch', nargs='+',
                       help='Process multiple files or patterns (e.g., *.mp4 *.mp3)')

    parser.add_argument('-p', '--prompt',
                       help='Add specific instructions (e.g., "extract 4 LinkedIn quotes")')

    parser.add_argument('-f', '--force', action='store_true',
                       help='Force regeneration, skip cached summaries')

    parser.add_argument('--no-email', action='store_true',
                       help='Skip email, save summary files only')

    parser.add_argument('-t', '--text', action='store_true',
                       help='Force article/text mode (override auto-detection)')

    parser.add_argument('--screenshots', action='store_true',
                       help='Force screenshot analysis for videos (requires ANTHROPIC_API_KEY)')

    parser.add_argument('--interval', type=int, default=30,
                       help='Screenshot interval in seconds (default: 30, for --screenshots mode)')

    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Show detailed processing logs')

    parser.add_argument('--model',
                       help='[Advanced] Claude model selection (requires API setup)')

    # Legacy options (still work but auto-detection makes them optional)
    parser.add_argument('--mp3',
                       help='[Legacy] Specify MP3 file (now auto-detected from path)')

    parser.add_argument('--transcript',
                       help='[Legacy] Specify transcript file (now auto-detected from .txt/.md)')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize processor with custom prompt if provided
    processor = PodcastProcessor(
        enable_email=not args.no_email,
        force_regenerate=args.force,
        model=args.model,
        custom_prompt=args.prompt
    )

    # Process based on input
    if args.batch:
        # Batch processing with smart detection
        for file_pattern in args.batch:
            for file_path in Path().glob(file_pattern):
                result = processor.smart_process(str(file_path))
                if result['success']:
                    # Extract and display metadata for batch processing
                    metadata = processor.extract_summary_metadata(result['summary'])
                    print(f"\n{'='*60}")
                    print(f"✅ Processed: {file_path.name}")
                    if metadata.get('podcast_name'):
                        print(f"   🎙️ {metadata['podcast_name']}")
                    if metadata.get('title'):
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
        # URL processing - use smart detection or forced mode
        force_type = None
        if args.screenshots:
            # Force screenshots mode for videos
            result = processor.process_video_screenshots(args.url, args.interval)
        elif args.text:
            # Force article mode
            force_type = 'article'
            result = processor.smart_process(args.url, force_type)
        else:
            # Smart auto-detection
            result = processor.smart_process(args.url)

        if result['success']:
            # Extract and display metadata
            metadata = processor.extract_summary_metadata(result['summary'])
            print(f"\n{'='*60}")

            # Show different metadata based on what we have
            if metadata.get('podcast_name'):
                print(f"🎙️  Podcast: {metadata['podcast_name']}")
            if metadata.get('title'):
                print(f"📝  Episode: {metadata['title']}")
            if metadata.get('episode_info'):
                print(f"👤  Guest: {metadata['episode_info']}")
            if metadata.get('core_insight'):
                print(f"\n💡  Core Insight:\n    {metadata['core_insight']}")
            if metadata.get('useful_because'):
                print(f"\n✅  Useful Because:\n    {metadata['useful_because']}")

            print(f"{'='*60}\n")
            print(f"✓ Files saved:")

            # Show files that exist
            if result.get('transcript_file'):
                print(f"  • Transcript: {result['transcript_file'].name}")
            if result.get('summary_file'):
                print(f"  • Summary: {result['summary_file'].name}")
            if result.get('frames_dir'):
                print(f"  • Frames: {result['frames_dir']}")
            if result.get('email_sent'):
                print(f"  • Email sent to {processor.email_config['email_to']}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()