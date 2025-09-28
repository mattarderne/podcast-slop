# Podcast Summarizer Configuration Guide

## 📝 Single Configuration File: `podcast_config.yaml`

We've simplified configuration from 2 confusing files to 1 clear file!

### Before (Confusing):
- `config.yaml` - User settings
- `prompts.yaml` - Also had user settings?? Plus prompts

### After (Simple):
- `podcast_config.yaml` - Everything in one place!

---

## 🚀 Quick Setup

1. **Edit `podcast_config.yaml`** with your details:

```yaml
profile:
  role: founder  # Your role (founder/investor/engineer)

  interests:
    - AI and machine learning
    - Your interests here

  goals:
    - What you want from podcasts

  context: |
    Brief description of what you're working on
```

2. **Run a podcast:**
```bash
podcast https://podcast-url.com
```

That's it! Summaries are now personalized for you.

---

## 📊 What Each Section Does

### Profile Section
Controls how Claude understands YOU:
- **role**: Changes entire sections (e.g., "Founder Insights" vs "Investor Insights")
- **interests**: Prioritizes relevant content
- **goals**: Focuses on what you want to achieve
- **context**: Provides background for better insights

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