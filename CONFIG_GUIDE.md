# Content Summarizer Configuration Guide

## 🚀 Quick Setup

1. **Edit `podcast_config.yaml`** with your details:

```yaml
profile:
  role: founder  # Your role (founder/investor/engineer)

  interests:
    - AI and machine learning
    - Your interests here

  goals:
    - What you want from content

  context: |
    Brief description of what you're working on
```

2. **Process any content:**
```bash
podcast https://youtube.com/watch?v=...  # Video
podcast https://example.com/article      # Article
podcast video.mp4                        # Local file
```

That's it! Summaries are now personalized for you.

The tool automatically detects whether you're processing a video, podcast, article, or local file and handles it appropriately.

---

## 📊 What Each Section Does

### Profile Section
Controls how Claude understands YOU (works for all content types):
- **role**: Changes section focus (e.g., "Founder Insights" for podcasts, "Actionable Takeaways" for articles)
- **interests**: Prioritizes relevant content and insights
- **goals**: Focuses on what you want to achieve
- **context**: Provides background for better personalized insights

### Preferences Section
Controls output format:
- **critical_rating**: Be harsh (true) or generous (false)
- **max_quotes**: How many quotes to extract (5-10)
- **prefer_metrics**: Emphasize numbers and data

### Email Section
Controls email behavior:
- **subject_prefix**: Emoji or text before subject
- **include_transcript**: Attach full transcript

---

## 🔄 Migration from Old Config

If you had old `config.yaml` or `prompts.yaml`:
1. Your settings have been preserved in `config.yaml.old` and `prompts.yaml.old`
2. Copy any custom settings to the new `podcast_config.yaml`
3. Delete the `.old` files when done

---

## 💡 Tips

1. **Be specific in your context** - The more Claude knows about your situation, the better the insights

2. **Update your goals regularly** - As your needs change, update the goals section

3. **Experiment with role** - Try different roles to get different perspectives on the same podcast

4. **Use --force to test changes**:
   ```bash
   podcast --transcript existing.txt --force
   ```

---

## 🛠️ Advanced Customization

For power users who want to modify prompts:

1. The prompts are now in the Python code (`get_default_prompts()` method)
2. To customize, you can:
   - Fork the code and modify the prompts directly
   - Or add a `custom_sections` list in the config:

```yaml
prompts:
  custom_sections:
    - "## LinkedIn Post Ideas"
    - "## Contrarian Takes"
```

---

## 📂 File Structure

```
podcasts/
├── podcast_config.yaml    # ← YOUR CONFIG (edit this!)
├── podcast_summarizer.py  # Main script
├── .env                   # Email settings
├── audio_files/          # Downloaded audio
├── transcripts/          # Transcribed text
└── summaries/            # Generated summaries
```

---

## ❓ FAQ

**Q: Do I need to edit the config?**
A: No, it works with defaults, but personalization makes summaries 10x more valuable

**Q: Can I have different configs for different projects?**
A: Currently uses one config, but you could swap `podcast_config.yaml` files

**Q: What if I break the YAML syntax?**
A: The tool will warn you and use defaults, so it won't break

**Q: How do I reset to defaults?**
A: Just delete or rename `podcast_config.yaml`