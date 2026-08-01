"""
Upstox OAuth2 Authentication Helper
Handles the OAuth2 flow to get access token from API key and secret
"""
import streamlit as st
import asyncio
from urllib.parse import urlencode
from loguru import logger
from api.upstox_client import get_client
from config import get

def get_oauth_url() -> str:
    """Generate OAuth authorization URL"""
    api_key = get("upstox.api_key", "")
    if not api_key:
        return ""
    
    params = {
        "client_id": api_key,
        "redirect_uri": "http://localhost:8501",
        "response_type": "code",
        "scope": "full_access",
    }
    return f"https://api.upstox.com/v2/login/authorization/dialog?{urlencode(params)}"

def show_oauth_setup():
    """Display OAuth setup instructions in Streamlit"""
    st.markdown("### 🔐 Upstox OAuth Setup")
    
    api_key = get("upstox.api_key", "")
    api_secret = get("upstox.api_secret", "")
    
    if not api_key or not api_secret:
        st.error("❌ API Key and API Secret not configured in Settings")
        st.info("""
        1. Go to Settings page
        2. Enter your Upstox API Key and API Secret
        3. Save settings
        4. Come back here
        """)
        return False
    
    st.success("✅ API credentials configured")
    
    # Show OAuth URL
    oauth_url = get_oauth_url()
    st.markdown("#### Step 1: Authorize")
    st.markdown(f"[Click here to authorize with Upstox]({oauth_url})")
    st.info("You'll be redirected to Upstox login. After login, you'll get an authorization code.")
    
    # Get auth code from user
    st.markdown("#### Step 2: Enter Authorization Code")
    auth_code = st.text_input(
        "Authorization Code",
        placeholder="Paste the code from redirect URL",
        type="password"
    )
    
    if st.button("✅ Verify & Save Token"):
        if not auth_code:
            st.error("Please enter the authorization code")
            return False
        
        with st.spinner("Exchanging code for access token..."):
            client = get_client()
            loop = asyncio.new_event_loop()
            try:
                success = loop.run_until_complete(client.get_token_from_credentials(auth_code))
                if success:
                    st.success("✅ Access token obtained successfully!")
                    st.info("Token will be valid for 24 hours. You'll need to repeat this process daily.")
                    
                    # Save to config
                    import yaml
                    from pathlib import Path
                    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
                    with open(config_path) as f:
                        cfg = yaml.safe_load(f) or {}
                    cfg.setdefault("upstox", {})
                    cfg["upstox"]["access_token"] = client.access_token
                    with open(config_path, "w") as f:
                        yaml.dump(cfg, f)
                    
                    st.rerun()
                else:
                    st.error("❌ Failed to exchange code for token. Check your credentials.")
                    return False
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                logger.error(f"OAuth error: {e}")
                return False
            finally:
                loop.close()
    
    return True

async def verify_and_refresh_token():
    """Verify token is valid, refresh if needed"""
    client = get_client()
    
    if not client.access_token:
        logger.warning("No access token available")
        return False
    
    is_valid = await client.verify_token()
    if not is_valid:
        logger.warning("Access token is invalid or expired")
        return False
    
    logger.info("Access token is valid")
    return True
