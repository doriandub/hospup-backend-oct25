# 🧠 OpenAI Setup for Viral Video Matching

## Overview
The viral video matching system uses OpenAI GPT-3.5-turbo to intelligently analyze and match user descriptions with viral video templates. This provides much better results than simple keyword matching.

## Railway Deployment Setup

### 1. Get OpenAI API Key
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key (starts with `sk-...`)

### 2. Configure Railway Environment Variable
1. Go to your Railway project dashboard
2. Navigate to **Variables** tab
3. Add new variable:
   - **Key**: `OPENAI_API_KEY`
   - **Value**: `sk-your-actual-openai-key-here`
4. Click **Save**

### 3. Verify Setup
The system will automatically:
- ✅ Try to use OpenAI GPT when available
- ✅ Fall back to intelligent keyword matching if OpenAI fails
- ✅ Log which system is being used

## Features

### 🎯 Smart Matching
- **Semantic Understanding**: Understands context, not just keywords
- **Hospitality Expertise**: Trained to understand hotel marketing concepts
- **Score + Reasoning**: Provides 0-10 score with explanation

### 🔄 Intelligent Fallback
- **No API Key**: Falls back to sophisticated keyword matching
- **API Failure**: Graceful degradation with logging
- **Rate Limits**: Automatic retry with exponential backoff

### 📊 Performance Optimized
- **Low Temperature**: Consistent scoring (0.1)
- **Token Limits**: Efficient API usage (150 tokens max)
- **Timeouts**: 10-second timeout for cloud reliability

## Example Analysis

**User Input**: *"Romantic dinner at sunset on our terrace"*

**GPT Analysis**:
```json
{
  "score": 8.7,
  "reasoning": "Perfect match - romantic ambiance, outdoor dining, sunset timing ideal for viral content"
}
```

**Fallback Analysis**:
```json
{
  "score": 0.75,
  "reasoning": "food_dining (high viral), title match (3 words), viral performance"
}
```

## Cost Estimation

**GPT-3.5-turbo Pricing** (as of 2024):
- ~$0.001 per request (150 tokens)
- 1000 searches = ~$1.00
- Very cost-effective for the intelligence gained

## Testing

Test the system works:
```bash
# Check logs for successful initialization
curl https://your-backend.up.railway.app/api/v1/viral-matching/stats

# Look for these log entries:
# ✅ "OpenAI client initialized successfully"
# ❌ "OPENAI_API_KEY not set, using intelligent fallback"
```

## Troubleshooting

### Common Issues

1. **Invalid API Key**
   - Error: `Invalid API key provided`
   - Solution: Double-check the key in Railway variables

2. **Rate Limits**
   - Error: `Rate limit exceeded`
   - Solution: System will automatically fall back

3. **Network Timeouts**
   - Error: `Timeout waiting for OpenAI response`
   - Solution: System falls back to intelligent matching

### Logs to Check

```bash
# Successful OpenAI usage
🧠 AI Analysis for: 'breakfast on terrace' (5 templates)
🎯 Hotel Paradise: score=0.847 - Perfect breakfast concept match
🏆 AI RANKING for 'breakfast on terrace'

# Fallback system usage
⚠️ OPENAI_API_KEY not set, using intelligent fallback system
🧠 AI Analysis for: 'breakfast on terrace' (5 templates)
🎯 Hotel Paradise: score=0.724 - food_dining (high viral), geo match
```

The system is designed to work seamlessly whether OpenAI is available or not!