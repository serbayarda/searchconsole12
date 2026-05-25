# Setup — read this once, top to bottom

You will do **3 things by hand** (irreducible — they involve your accounts), and a script does the rest.

```
1. Get an Anthropic API key            (~1 min)
2. Get a Google OAuth client_secret    (~5 min, one-time)
3. Run setup.sh, then run the agent    (~1 min)
```

That's it. If any step trips you up, copy the exact error message and ask me about it.

---

## 1. Get an Anthropic API key

1. Open <https://console.anthropic.com/settings/keys>
2. Sign in (create an account if you don't have one).
3. Add a payment method under **Plans & Billing** (a few dollars is plenty to test).
4. Click **Create Key** → copy the value (starts with `sk-ant-...`). **You can only see it once.**

Keep that string in a safe place for step 3.

---

## 2. Get a Google OAuth client (one-time, ~5 min)

This lets the agent read **your** Search Console data. You only do this once.

### 2a. Create / pick a Google Cloud project

1. Open <https://console.cloud.google.com/>
2. Top bar → project dropdown → **New Project** → name it anything (e.g. `gsc-agent`) → **Create**.
3. Make sure the new project is selected in the top bar.

### 2b. Enable the Search Console API

1. Open <https://console.cloud.google.com/apis/library/searchconsole.googleapis.com>
2. Click **Enable**.

### 2c. Configure the OAuth consent screen

1. Open <https://console.cloud.google.com/apis/credentials/consent>
2. User Type → **External** → **Create**.
3. Fill the required fields:
   - App name: `GSC Agent` (anything)
   - User support email: your email
   - Developer contact email: your email
   - Leave everything else blank → **Save and Continue**.
4. **Scopes** screen → **Save and Continue** (don't add any).
5. **Test users** screen → **Add Users** → add **your own Gmail address** → **Save and Continue**.
6. **Summary** → **Back to Dashboard**.

> Because the app is in "Testing" mode, only the test users you added can sign in. That's fine — you're the only user.

### 2d. Create the OAuth client credentials

1. Open <https://console.cloud.google.com/apis/credentials>
2. **Create Credentials** → **OAuth client ID**.
3. **Application type: Desktop app**. Name: `gsc-agent-desktop`. → **Create**.
4. A dialog appears with the new client. Click **Download JSON**.
5. **Rename the downloaded file to `client_secret.json`** and move it into this repo's root folder (the folder that has `README.md` in it).

You should now have two things ready: an `sk-ant-...` key and a `client_secret.json` file.

---

## 3. Run the setup script, then the agent

### macOS / Linux

```bash
cd path/to/searchconsole12
./setup.sh
```

The script will:
- create a Python virtualenv in `.venv/`
- install all dependencies
- create `.env` from the template
- tell you what's still missing

Then open `.env` in any text editor and replace the placeholder with your real key:

```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Now run:

```bash
source .venv/bin/activate
python -m src.cli
```

### Windows (PowerShell)

```powershell
cd path\to\searchconsole12
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env       # paste your ANTHROPIC_API_KEY, save
python -m src.cli
```

(Make sure `client_secret.json` is in the folder before running.)

---

## What happens on first run

1. You'll see `Search Console AI Agent — ask anything about your GSC data.`
2. Type a question, e.g. **`list my properties`**.
3. A **browser tab opens** asking you to sign in with Google and approve the agent.
4. After "The authentication flow has completed", switch back to the terminal. A `token.json` file is created — the agent will reuse it forever, no more browser pop-ups.
5. The agent prints your GSC properties. Now ask whatever you want:
   - `Top 10 queries by clicks in the last 28 days for https://yoursite.com/`
   - `Which pages dropped the most clicks vs the previous 28 days?`
   - `Find striking-distance keywords (positions 5–15 with over 500 impressions)`
   - `Pages with high impressions but CTR under 1%`

---

## Common errors and the fix

| Message | What to do |
| --- | --- |
| `FileNotFoundError: client_secret.json` | Re-do step 2d. The file must be in the repo root, named exactly `client_secret.json`. |
| `ANTHROPIC_API_KEY not set` | Edit `.env` and paste your real key (no quotes). |
| `access_denied` in the browser | Step 2c was incomplete — add your Gmail under **Test users**. |
| `403: Search Console API has not been used` | Step 2b — enable the API. |
| `User does not have sufficient permissions for site` | The Google account you signed in with isn't a verified owner / user on that GSC property. Add it in Search Console → Settings → Users and permissions. |
| `quota exceeded` | GSC has daily quotas; wait a bit or narrow your date range. |

If you hit something not on this list, copy the **full error message** and ask me — I'll fix it.
