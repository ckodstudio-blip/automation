# Natural voice + moving graphics update

এই প্যাচের তিনটি Python ফাইল GitHub repository-এর একই path-এ replace/add করুন:
- autoshorts/engine.py (আগের diagnostics fix সহ)
- autoshorts/video.py (replace)
- autoshorts/voice.py (নতুন)

.github/workflows/shorts.yml-এর job env: অংশে নিচের তিনটি line যোগ করুন। একই indentation ব্যবহার করুন:

    TTS_MODEL: ${{ vars.TTS_MODEL || 'gemini-3.8-flash-lite-tts' }}
    TTS_VOICE: ${{ vars.TTS_VOICE || 'Kore' }}
    LANGUAGE: ${{ vars.LANGUAGE || 'bn' }}

LANGUAGE আগে থাকলে নতুন আরেকটি নয়, আগের line-টি edit করুন।
Settings > Secrets and variables > Actions > Variables:
TTS_MODEL = gemini-3.8-flash-lite-tts
TTS_VOICE = Kore
LANGUAGE = bn (বাংলা) অথবা en (ইংরেজি)
GEMINI_MODEL আগের working script model-ই রাখুন। TTS_MODEL আলাদা।

নতুন API key লাগে না: GEMINI_API_KEY ব্যবহার করে। তবে TTS model access/quota দরকার।
Gemini TTS free/unlimited ধরে নেবেন না। AI Studio-তে access ও pricing যাচাই করুন।
এই প্যাচ নিজে billing চালু করে না। Voice API error হলে upload বন্ধ হবে; robotic fallback নেই।

Actions > Auto Shorts > Run workflow > private দিয়ে নতুন run শুরু করুন। Re-run jobs নয়।
Voice শুনে এবং video দেখে সন্তুষ্ট হলে public করতে পারেন।

এতে natural AI narration, চলমান orbit/particles/progress এবং subtitles আছে।
এটি topic-specific AI footage বা cinematic video নয়; educational motion graphics।
Subtitles-এর timing আনুমানিক; speech-to-text word alignment ব্যবহার করা হয়নি।
প্রতি scene-এ আলাদা TTS request হয়। 429/5xx হলে সর্বোচ্চ ৩ বার চেষ্টা করে।
পুরনো espeak-ng workflow dependency সরানো বাধ্যতামূলক নয়, এখন আর ব্যবহার হয় না।

Validation: mocked API response parsing/retry/failure এবং FFmpeg smoke render locally checked।
কোনো real Gemini voice call বা YouTube upload করা হয়নি; production voice quality আপনার private test-এ যাচাই করতে হবে।
