# AutoShorts Actions — VPS ছাড়াই YouTube Shorts

GitHub Actions-এ নির্দিষ্ট সময়ে একটি Python job: AI বিষয়/script/title/description/tags/hashtags লিখবে → original abstract motion cards ও offline voice/subtitles বানাবে → YouTube-এ upload → temporary media delete। Aiven MySQL-এ encrypted OAuth token ও history থাকবে। Pexels/Pixabay, Render, UptimeRobot বা নিজের PC চালু রাখতে হবে না।

**Visual style:** abstract geometric motion graphics, English scene labels, narration-language captions; stock footage বা text-to-video AI footage নয়। Bengali narration/subtitles সমর্থিত কিন্তু voice basic/robotic। Scene prompts তৈরি ও সংরক্ষণ হয়; renderer সেই prompt দিয়ে নতুন AI footage বানায় না।

## ১. GitHub repo তৈরি ও code upload
1. নতুন **Private** repo তৈরি করুন: `auto-shorts`।
2. ZIP extract করে এই ফোল্ডারের **ভেতরের সব file/folder** repo root-এ upload করুন। ZIP নিজে upload করলে workflow চলবে না।
3. বিশেষ করে `.github/workflows/shorts.yml` থাকতে হবে। Windows-এ dot-folder বাদ পড়লে GitHub → Add file → Create new file → নাম `.github/workflows/shorts.yml` দিয়ে ZIP-এর ওই file-এর text paste করুন।
4. Default branch (সাধারণত main)-এ code রাখুন। কোনো secret source file-এ দেবেন না।

## ২. Aiven MySQL
Aiven MySQL service-এর Connection information থেকে hostname, port, user/password, database নিন। Project CA certificate `ca.pem` download করুন। তার পুরো certificate text GitHub secret-এ দেবেন। PostgreSQL credentials এখানে নয়।

প্রথম job নিজে `autoshorts_jobs` ও `autoshorts_settings` তৈরি করে। User-এর CREATE/SELECT/INSERT/UPDATE permission লাগবে। TLS CA ও hostname verification চালু থাকে। Network/IP restrictions থাকলে GitHub-hosted runner connectivity লাগবে; runner outbound IP পরিবর্তিত হতে পারে। অন্য business database-এর বদলে আলাদা database/user ভালো।

পুরনো Render সংস্করণের একই schema ব্যবহার করা যায়; একই সময়ে পুরনো scheduler চালাবেন না। Actions চালু করার আগে Render service/automation বন্ধ করুন। একই database ও একই SECRET_KEY হলে saved encrypted token পড়তে পারে।

## ৩. Gemini API
https://aistudio.google.com/apikey থেকে key নিন। Account-এ generateContent ও JSON response সমর্থিত text model-এর ID বেছে GEMINI_MODEL variable-এ দেবেন। Free tier/quota model ও account অনুযায়ী; এই code paid fallback করে না। 429 হলে run ব্যর্থ হবে।

## ৪. YouTube প্রথম authorization (server ছাড়াই)
1. https://console.cloud.google.com/ → project তৈরি → Library → **YouTube Data API v3 Enable**।
2. Google Auth Platform → consent/branding/audience সেটআপ। External/Testing হলে নিজের Gmail Test users-এ যোগ করুন।
3. Clients → Create OAuth Client → **Web application**।
4. Authorized redirect URIs-এ দিন: `https://developers.google.com/oauthplayground`
5. Client ID ও Client Secret সংরক্ষণ করুন।
6. https://developers.google.com/oauthplayground/ খুলুন → gear/settings → **Use your own OAuth credentials** → নিজের Client ID/Secret বসান। OAuth flow server-side এবং access type offline রাখুন; consent prompt দিন।
7. Scope লিখুন: `https://www.googleapis.com/auth/youtube.upload`
8. Authorize APIs → নিজের সঠিক YouTube channel account দিয়ে অনুমতি দিন।
9. **Exchange authorization code for tokens** → পাওয়া **Refresh token** GitHub secret-এ রাখুন। এটি access token নয়। নিজের credentials ব্যবহার না করলে Playground token অস্থায়ী হতে পারে।
10. External app Testing থাকলে refresh token সাধারণত ৭ দিনে expire হতে পারে; প্রয়োজন অনুযায়ী Google publishing/verification সম্পূর্ণ করুন। Revoked/expired token হলে নতুন token নিন। Initial consent একবার নিজে দিতে হবে।

## ৫. GitHub Secrets
Repo → Settings → Secrets and variables → Actions → **Secrets → New repository secret**।

| Secret | Value |
|---|---|
| GEMINI_API_KEY | Gemini key |
| GOOGLE_CLIENT_ID | নিজের OAuth Client ID |
| GOOGLE_CLIENT_SECRET | সেই Client Secret |
| YOUTUBE_REFRESH_TOKEN | Playground থেকে পাওয়া refresh token |
| SECRET_KEY | অন্তত ৩২ random characters; স্থায়ীভাবে একই রাখুন |
| MYSQL_HOST | Aiven MySQL hostname |
| MYSQL_PORT | Aiven service-এর port |
| MYSQL_USER | Aiven user |
| MYSQL_PASSWORD | Aiven password |
| MYSQL_SSL_CA | পুরো ca.pem certificate text, BEGIN/END সহ |

Token Aiven-এ SECRET_KEY দিয়ে encrypted অবস্থায় থাকে। SECRET_KEY বদলালে পুরনো token decrypt হবে না। প্রথম run-এ YOUTUBE_REFRESH_TOKEN দিয়ে bootstrap হয়; পরের run-এ Aiven token ব্যবহৃত হয়। Token বদলাতে workflow manual run-এর **reset_token=true** নির্বাচন করুন, আগে GitHub secret-এ নতুন token বসান।

## ৬. GitHub Variables
একই Settings page → **Variables → New repository variable**।

| Variable | Suggested value |
|---|---|
| GEMINI_MODEL | account-এ পাওয়া JSON-supported text model ID; অবশ্যই পূরণ করুন |
| MYSQL_DATABASE | defaultdb |
| NICHE | Nature and space facts for curious beginners |
| LANGUAGE | en অথবা bn |
| UPLOAD_PRIVACY | প্রথমে private; পরীক্ষা শেষে public |
| ENABLE_SCHEDULE | প্রথমে false; পরে true |
| MADE_FOR_KIDS | false; সত্যিই শিশুদের উদ্দেশ্যে ভিডিও হলে true |
| CONTAINS_SYNTHETIC_MEDIA | false; YouTube disclosure প্রযোজ্য হলে true |

ADMIN_USER, ADMIN_PASSWORD, PUBLIC_URL, PEXELS_API_KEY বা PIXABAY_API_KEY লাগবে না। কোনো web dashboard নেই—Actions run summary ও Aiven history ব্যবহার করুন।

## ৭. প্রথম পরীক্ষা
Repo → Actions → **Auto Shorts** → Run workflow → privacy **private** → Run workflow।

Workflow steps:
- Python environment
- FFmpeg, espeak-ng ও fonts install
- Python dependencies install
- AI script → original motion graphics → speech/captions → upload
- সব temporary media cleanup

Success হলে Actions summary-তে YouTube link পাবেন। ভিডিও শুধু YouTube-এ থাকবে; কোনো downloadable artifact/video backup রাখা হয় না। YouTube Studio-তে narration, captions, topic ও visuals যাচাই করুন। Basic speech quality পছন্দ না হলে professional TTS integration পরবর্তী কাজ।

## ৮. প্রতিদিন অটো publish
পরীক্ষার পরে Variables → UPLOAD_PRIVACY=public এবং ENABLE_SCHEDULE=true দিন।

Default schedule: **প্রতিদিন বাংলাদেশ সময় রাত ৮:১৭**। `.github/workflows/shorts.yml`-এ cron `'17 14 * * *'` (UTC 14:17)। ভিন্ন সময় চাইলে cron সম্পাদনা করুন। Default branch-এ workflow রাখতে হবে।

Schedule GitHub load-এর জন্য দেরি হতে বা বাদ পড়তে পারে। Public repo-তে দীর্ঘ নিষ্ক্রিয়তার পরে scheduled workflow disable হতে পারে। Private repo-তে included Actions minutes/storage plan অনুযায়ী; API usage আলাদা। নিরবচ্ছিন্ন/একদম নির্দিষ্ট সময়ের SLA নেই। Actions usage/budget দেখুন; এই project সার্ভার হিসেবে runner চালু রাখে না, প্রতি job শেষে বন্ধ হয়।

## Duplicate ও failure handling
- Repository concurrency group একসঙ্গে একটি publisher job চালায়। একই DB ব্যবহার করে অন্য repo/Render parallel চালাবেন না।
- Scheduled slot প্রতি Dhaka date-এ unique। Actions-এর Re-run একই manual run ID-তে পুনরায় upload করে না। নতুন manual Run workflow নতুন job।
- AI আগের ৫০ title দেখে; exact duplicate title প্রত্যাখ্যান। একই topic নতুন wording-এ ফিরতে পারে।
- Network/API error হলে automatic retry/premium fallback নেই।
- `needs_check`: upload সফল হয়ে response হারিয়ে যেতে পারে। YouTube Studio দেখুন; blind retry করবেন না।
- Next run startup পুরনো queued/generating/uploading status-কে needs_check করে। Failed generation এবং uncertain upload আলাদা নিরীক্ষণ করতে Aiven error column দেখুন।
- Token expire হলে refresh করে encrypted value Aiven-এ save করে। Secret values stdout/log-এ দেখানো হয় না।
- Successful upload নিশ্চিত হলেই local final video delete। Failure/cancel হলেও workflow-এর always cleanup step temporary directory delete করে। Runner teardown-ও ephemeral; ভিডিও backup নেই।

## Aiven history দেখা
SQL console/client-এ:
```sql
SELECT id, state, title, video_id, error, created
FROM autoshorts_jobs
ORDER BY created DESC
LIMIT 30;
```
Script ও prompts JSON `autoshorts_settings`-এর `plan:<job-id>` key-তে থাকে। Token ওই table-এ encrypted; সেটি শেয়ার করবেন না। Metadata history auto-purge নেই।

## সীমা
- Output 720×1280, 25fps; 3–5 scenes; প্রায় 30–70 seconds।
- Full cinematic footage বা AI-generated actors/scenes নয়: animated fact cards with slow zoom and captions।
- Spoken language en/bn; large scene labels English; captions narration অনুযায়ী।
- espeak-ng offline voice; music নেই।
- Title/tags AI-generated, live trend/search-volume data নেই; views/ranking/monetization guaranteed নয়।
- Model কখনো ভুল তথ্য লিখতে পারে। Public automation-এর আগে niche ও output যাচাই করুন।
- Gemini free quota, Actions compute quota, Aiven storage/availability নিজের plan অনুযায়ী।

## Tests ও validation
`python -m pip install -r requirements.txt`

`python -m unittest discover -s tests -v`

Tests explicitly use temporary SQLite; production defaults to MySQL with verified TLS। Real FFmpeg tests exercise portrait motion, captions, audio, concat and probing using a synthetic audio fixture। Cloud APIs, Aiven live connectivity ও GitHub actual run আপনার credentials ছাড়া পরীক্ষা করা হয়নি। Included offline speech requires espeak-ng, installed by workflow।

## Repo files
- `.github/workflows/shorts.yml`: daily/manual publisher ও cleanup
- `autoshorts/cli.py`: একবার কাজ চালিয়ে exit
- `autoshorts/engine.py`: AI, metadata, token, YouTube ও job pipeline
- `autoshorts/video.py`: original graphics, offline speech ও FFmpeg
- `autoshorts/storage.py`: Aiven TLS/MySQL ও test-only SQLite
- `tests/test_core.py`: meaningful workflow/media tests
- `.env.example`: configuration reference; workflow reads GitHub Secrets/Variables directly
