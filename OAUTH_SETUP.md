# OAuth Setup Guide for NiftyScanner

## Getting Upstox API Credentials

### Step 1: Create Upstox Account
1. Go to https://upstox.com
2. Sign up for a free account
3. Complete KYC verification

### Step 2: Create API Application
1. Login to Upstox
2. Go to Developer Settings / API Console
3. Create a new application
4. You'll get:
   - **API Key** (Client ID)
   - **API Secret** (Client Secret)

### Step 3: Configure in NiftyScanner

#### Local Setup:
1. Open NiftyScanner app
2. Go to **Settings** → **API Keys** tab
3. Enter your API Key and API Secret
4. Click "Save API Credentials"
5. Go to **Settings** → **OAuth Setup** tab
6. Click the authorization link
7. Login with your Upstox account
8. Copy the authorization code from the redirect URL
9. Paste it in the text field
10. Click "Verify & Save Token"

#### Streamlit Cloud Setup:
1. Go to your app settings
2. Add secrets:
```toml
UPSTOX_API_KEY = "your_api_key_here"
UPSTOX_API_SECRET = "your_api_secret_here"
```
3. Users will need to complete OAuth setup in the app (Settings → OAuth Setup)

## How It Works

1. **API Key & Secret**: Used to authenticate your application with Upstox
2. **OAuth Flow**: 
   - User clicks authorization link
   - Logs in with Upstox account
   - Grants permission to NiftyScanner
   - Gets authorization code
   - Code is exchanged for access token
3. **Access Token**: Used to fetch market data (valid for 24 hours)

## Token Expiration

- Access tokens expire after **24 hours**
- You'll need to repeat the OAuth setup daily
- The app will show an error if token is expired
- Simply go to Settings → OAuth Setup and get a new token

## Troubleshooting

**"Invalid API Key or Secret"**
- Check your credentials in Settings → API Keys
- Ensure they're copied correctly from Upstox

**"Authorization code is invalid"**
- Make sure you copied the full code from the redirect URL
- Try again with a fresh authorization

**"Token exchange failed"**
- Check your internet connection
- Verify API credentials are correct
- Try again in a few moments

## Security Notes

- Never share your API Secret
- API credentials are stored locally in `config/config.yaml`
- On Streamlit Cloud, use the Secrets feature
- Access tokens are temporary and expire daily
