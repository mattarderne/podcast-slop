#!/usr/bin/env python3
"""
Process existing MP3 files with the podcast summarizer
"""

import sys
from pathlib import Path
from podcast_summarizer import PodcastProcessor


def main():
    """Main function for batch processing"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Process existing MP3 files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s audio.mp3                    # Process single file
  %(prog)s --all                        # Process all MP3s in audio_files/
  %(prog)s --dir /path/to/mp3s          # Process all MP3s in directory
        """
    )

    parser.add_argument('mp3_file', nargs='?', help='MP3 file to process')
    parser.add_argument('--all', action='store_true', help='Process all MP3s in audio_files/')
    parser.add_argument('--dir', help='Process all MP3s in specified directory')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')

    args = parser.parse_args()

    # Initialize processor
    processor = PodcastProcessor()

    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    files_to_process = []

    if args.all:
        # Process all MP3s in audio_files directory
        audio_dir = Path("audio_files")
        if not audio_dir.exists():
            print("No audio_files directory found")
            sys.exit(1)
        files_to_process = list(audio_dir.glob("*.mp3"))

    elif args.dir:
        # Process all MP3s in specified directory
        target_dir = Path(args.dir)
        if not target_dir.exists():
            print(f"Directory not found: {args.dir}")
            sys.exit(1)
        files_to_process = list(target_dir.glob("*.mp3"))

    elif args.mp3_file:
        # Process single file
        mp3_path = Path(args.mp3_file)
        if not mp3_path.exists():
            print(f"File not found: {args.mp3_file}")
            sys.exit(1)
        files_to_process = [mp3_path]

    else:
        # Show available MP3s
        mp3_files = list(Path(".").glob("*.mp3")) + list(Path("audio_files").glob("*.mp3"))
        if mp3_files:
            print(f"Found {len(mp3_files)} MP3 file(s):")
            for i, f in enumerate(mp3_files[:10], 1):
                print(f"  {i}. {f}")
            if len(mp3_files) > 10:
                print(f"  ... and {len(mp3_files) - 10} more")
            print("\nUsage:")
            print(f"  {sys.argv[0]} {mp3_files[0]}")
            print(f"  {sys.argv[0]} --all")
        else:
            parser.print_help()
        sys.exit(1)

    # Process files
    if not files_to_process:
        print("No MP3 files found to process")
        sys.exit(1)

    print(f"\nProcessing {len(files_to_process)} file(s)...")
    print("=" * 60)

    success_count = 0
    for mp3_file in files_to_process:
        print(f"\n📎 Processing: {mp3_file.name}")
        print("-" * 40)

        result = processor.process_mp3(mp3_file)

        if result['success']:
            success_count += 1
            print(f"✅ Success!")
            print(f"   ID: {result['id']}")
            print(f"   Transcript: {result['transcript_file'].name}")
            print(f"   Summary: {result['summary_file'].name}")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")

    print("\n" + "=" * 60)
    print(f"Completed: {success_count}/{len(files_to_process)} files processed successfully")


if __name__ == "__main__":
    main()