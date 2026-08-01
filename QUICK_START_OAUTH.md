# Quick Start: OAuth Setup

## For Local Users

### 1. Get Upstox API Credentials
- Go to https://upstox.com → Developer Settings
- Create an API application
- Copy your **API Key** and **API Secret**

### 2. Configure in NiftyScanner
```bash
streamlit run app.py
```

### 3. In the App
1. Click **Settings** (bottom right)
2. Enter password: `Pragu1020$`
3. Go to **API Keys** tab
4. Paste your API Key and API Secret
5. Click **Save API Credentials**

### 4. Get Access Token
1. Go to **OAuth Setup** tab
2. Click the blue authorization link
3. Login with your Upstox account
4. You'll see a redirect URL with a code
5. Copy the code (after `code=`)
6. Paste it in the text field
7. Click **Verify & Save Token**
8. ✅ Done! Token is saved

## For Streamlit Cloud Users

### 1. Get Upstox API Credentials
- Same as above

### 2. Deploy to Streamlit Cloud
```bash
git push origin main
```

### 3. Add Secrets in Streamlit Cloud
- Go to your app settings
- Click **Secrets**
- Add:
```toml
UPSTOX_API_KEY = "your_api_key_here"
UPSTOX_API_SECRET = "your_api_secret_here"
```

### 4. Users Complete OAuth Setup
- Users open the app
- Go to Settings → OAuth Setup
- Follow steps 2-7 from "For Local Users" section

## Token Expiration

- Tokens expire after **24 hours**
- When expired, you'll see an error
- Simply repeat the OAuth Setup process
- Takes less than 1 minute

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Invalid API Key" | Check credentials in Settings → API Keys |
| "Authorization code invalid" | Copy the full code from redirect URL |
| "Token exchange failed" | Check internet connection, try again |
| "No access token" | Complete OAuth Setup in Settings |

## What's Different from Before?

**Before:** Users needed to manually generate access token from Upstox dashboard

**Now:** Users only need API Key and Secret, token is generated automatically in the app

**Benefit:** Simpler setup, no manual token management needed
