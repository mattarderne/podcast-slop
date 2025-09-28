# Prompt Comparison: Before vs After YAML Config

## 🔴 BEFORE (Hardcoded - Generic for Everyone)

### Summary Section
```
## Founder Insights
Identify 2 specific pieces of information that would be particularly valuable for founders/entrepreneurs:
• Focus on tactical advice, non-obvious lessons, or specific strategies
```

### Synthesis
```
CORE_INSIGHT: [One sentence that captures the non-obvious, most valuable insight from this conversation - be specific, not generic]
USEFUL_BECAUSE: [2-3 sentences explaining why this insight matters and how it can be applied practically.]
```

**Problems:**
- ❌ Always assumes user is a founder
- ❌ No consideration of user's specific context
- ❌ Generic advice for all users
- ❌ Can't adapt to different roles (investor, engineer, etc.)

---

## 🟢 AFTER (YAML Config - Personalized)

### Summary Section with Variables
```
## Insights for {user_role}
Based on the user's role as a {user_role}, identify 2-3 specific pieces of information that would be particularly valuable:
• Connect to the user's goals: {user_goals}
• Prioritize points relevant to: {user_interests}
• Specifically highlight what's relevant for someone who: {user_context}
```

### Enhanced Synthesis with Context
```
CORE_INSIGHT: [One sentence... Focus on what would matter most to someone with the user's interests: {user_interests}]
USEFUL_BECAUSE: [2-3 sentences... What specific problem does it solve given their goals: {user_goals}?]
```

**Benefits:**
- ✅ Adapts to ANY role (founder, investor, engineer, student)
- ✅ Incorporates YOUR specific interests
- ✅ Connects to YOUR stated goals
- ✅ Considers YOUR context (what you're building)

---

## 📊 Real Example Transformation

### Before (Generic):
> "Tom uses AI to process podcasts efficiently"

### After (Personalized for you as founder in dev tools):
> "Tom discovered that general-purpose LLMs consistently outperformed specialized ML libraries... revealing that the winning GTM strategy is building flexible, prompt-based developer tools priced per workflow"

---

## 🎯 Key Additions in YAML Config

1. **USER CONTEXT Section** (New)
   - Added at the beginning of prompt
   - Tells Claude about YOU specifically

2. **Dynamic Replacements** (New)
   - `{user_role}` - Your role (founder/investor/etc)
   - `{user_interests}` - Your specific interests
   - `{user_goals}` - What you want to achieve
   - `{user_context}` - Your background/project

3. **Targeted Questions** (Enhanced)
   - "What matters to someone with user's interests"
   - "What problem does it solve for their goals"
   - "Relevant for someone who [user context]"

4. **Critical Rating Context** (Enhanced)
   - Rates usefulness FOR YOUR ROLE
   - Considers actionability FOR YOUR CONTEXT

---

## 💡 The Big Difference

**BEFORE:** One-size-fits-all summaries that assume everyone is a founder wanting generic startup advice

**AFTER:** Tailored summaries that understand:
- WHO you are
- WHAT you're building
- WHY you're listening
- HOW to make it actionable for YOU

The prompts now act like a personal analyst who knows your background rather than a generic summarizer!