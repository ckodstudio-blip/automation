# AutoShorts — Blender 3D update

এটি আপনার আগের GitHub Actions AutoShorts project-এর update।
Original low-poly 3D Mira/Rafi কোডেই বানানো হয়; আলাদা .blend/character download লাগে না।

## ১. কোন ফাইল কোথায় দেবে
ZIP খুলে repository-র একই path-এ দিন:

| Path | কাজ |
|---|---|
| autoshorts/engine.py | replace: ১ মিনিটের 3D গল্প ও metadata |
| autoshorts/video.py | replace: Blender render + voice/subtitles |
| autoshorts/voice.py | replace: পুরো গল্পের voice এক request |
| autoshorts/timing.py | replace/add: আনুমানিক scene timing |
| autoshorts/render3d.py | নতুন: Blender চালায় |
| autoshorts/blender_scene.py | নতুন: character, scene ও movement |
| scripts/preview_3d.py | নতুন: API ছাড়া silent test |
| .github/workflows/shorts.yml | replace: Blender install ও automation |

আগের storage.py, cli.py, __init__.py, requirements.txt রাখবেন।
আগের cartoon.py থাকলেও সমস্যা নেই; নতুন renderer সেটি ব্যবহার করে না।
নতুন SQL/API key/secret লাগবে না। আগের Aiven ও YouTube credentials কাজ করবে।

## ২. প্রথমে preview চালাও
সব ফাইল Commit করার পরে:
Actions > Auto Shorts > Run workflow।
'preview_only' checkbox checked রাখুন (নতুন workflow-তে default checked)।
এটি ৬ সেকেন্ডের silent sample বানাবে; Gemini, database বা YouTube call করবে না।
সফল হলে ওই run-এর Summary > Artifacts > cartoon-3d-preview download করে দেখুন।
Preview artifact ৩ দিন রাখা হয়। আসল uploaded video artifact হিসেবে রাখা হয় না।

## ৩. আসল ১ মিনিটের video
Preview ঠিক হলে আবার নতুন Run workflow:
- preview_only checkbox UNCHECK করুন।
- প্রথমবার visibility private দিন।
- Run workflow দিন।
এবার Gemini গল্প/voice, Aiven history ও YouTube upload চালু হবে।
Voice ৫০–৭০ সেকেন্ড হলে pitch না বদলে গতি সামান্য মিলিয়ে চূড়ান্ত ৬০ সেকেন্ড হয়।
এই সীমার বাইরে voice হলে dialogue না কেটে upload-এর আগে থামে।
Scene/subtitle timing আনুমানিক; মুখ audio volume অনুযায়ী নড়ে, নিখুঁত lip-sync নয়।
TTS429 এলে পুনরায় request দেয় না; quota reset হলে পরে নতুন run করুন।

## ৪. Variables
আগের settings ঠিক থাকলে নতুন variable লাগে না:
LANGUAGE=bn
MADE_FOR_KIDS=true (এই শিশুদের cartoon-এর জন্য)
NICHE=বাচ্চাদের গল্পের আগের value
GEMINI_MODEL=আপনার working script model
TTS_MODEL=gemini-3.8-flash-lite-tts
TTS_VOICE=Kore
TTS_SECOND_VOICE=Puck
UPLOAD_PRIVACY=private বা public
ENABLE_SCHEDULE=true হলে প্রতিদিন বাংলাদেশ সময় রাত ৮:১৭-এ পূর্ণ video generation হবে।
পুরনো custom cron থাকলে নতুন workflow-র cron নিজের সময়মতো বদলাবেন।
Scheduled run preview_only ব্যবহার করে না; পূর্ণ generation/upload চালায়।
পরীক্ষার সময় schedule বন্ধ চাইলে ENABLE_SCHEDULE=false রাখুন; পরে true করুন।

## ৫. Render-এর সীমা
Preset scenes: park, space, lab। Actions: talk, wave, point, walk, celebrate।
Original characters: দুইটি সাধারণ low-poly 3D বন্ধু, blink ও amplitude-driven mouth।
Camera সামান্য orbit করে। arbitrary prompt থেকে নতুন object/character বানায় না।
CPU Cycles render: 360x640, 12fps, 8 samples, denoising; final file 720x1280-তে upscale হয়।
এটি native 720p বা photoreal cinematic rendering নয়। পরিষ্কার সহজ 3D cartoon।
এক মিনিটে ৭২০টি frame render হয়; runner-এর ওপর নির্ভর করে অনেক সময় লাগতে পারে।
Blender render limit ১৫০ মিনিট, job limit ১৮০ মিনিট। GitHub compute allowance খরচ হয়।
খরচ ছাড়া চলা GitHub allowance ও Gemini quota-এর মধ্যে থাকার ওপর নির্ভর করে।

## Validation
সংযুক্ত VALIDATION.txt-এ কোন check বাস্তবে চালানো হয়েছে ও সীমাবদ্ধতা লেখা আছে।
GitHub runner-এর গতি স্থানীয় test-এর সঙ্গে এক নাও হতে পারে।
Blender reference: https://docs.blender.org/manual/en/4.1/advanced/command_line/arguments.html
