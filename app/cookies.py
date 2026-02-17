"""
Clean, simple cookie-based session management.

After registration and login, user session is stored in a browser cookie
that persists across page refreshes, browser restarts, and app redeployments.

The cookie contains encrypted session data with the following flow:
1. User logs in successfully -> create session token in database
2. Store session data in browser cookie
3. On page reload -> read cookie and restore session automatically
4. Session token is validated against database on restore
5. Logout -> clear cookie and database session
"""

import streamlit as st
import streamlit.components.v1 as components
import base64
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from app import db, sessions


# JavaScript for reading/writing cookies
JS_GET_COOKIE = """
<script>
function getCookie(name) {
    const nameEQ = name + "=";
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
        let c = cookies[i].trim();
        if (c.indexOf(nameEQ) === 0) {
            return c.substring(nameEQ.length);
        }
    }
    return null;
}
window.parent.postMessage({
    type: 'cookie_data',
    value: getCookie('yln_session')
}, '*');
</script>
"""

JS_SET_COOKIE = """
<script>
function setCookie(name, value, days) {{
    const date = new Date();
    date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
    const expires = "expires=" + date.toUTCString();
    document.cookie = name + "=" + value + ";" + expires + ";path=/;SameSite=Lax";
}}
setCookie('yln_session', '{cookie_value}', {days});
</script>
"""

JS_DELETE_COOKIE = """
<script>
document.cookie = "yln_session=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
</script>
"""


def _encode_session_data(session_data: Dict[str, Any]) -> str:
    """Encode session data to base64 JSON for cookie storage."""
    json_str = json.dumps(session_data)
    return base64.b64encode(json_str.encode()).decode()


def _decode_session_data(cookie_value: str) -> Optional[Dict[str, Any]]:
    """Decode session data from cookie."""
    try:
        json_str = base64.b64decode(cookie_value.encode()).decode()
        return json.loads(json_str)
    except Exception as e:
        print(f"Failed to decode session cookie: {e}")
        return None


def set_session_cookie(user_id: int, session_token: str, days: int = 30) -> None:
    """
    Set session cookie in browser.
    
    Args:
        user_id: The user's ID
        session_token: The session token from database
        days: Cookie expiry in days (default 30)
    """
    session_data = {
        "user_id": user_id,
        "session_token": session_token,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    cookie_value = _encode_session_data(session_data)
    js_code = JS_SET_COOKIE.format(cookie_value=cookie_value, days=days)
    components.html(js_code, height=0)


def get_session_cookie() -> Optional[Dict[str, Any]]:
    """
    Get session data from browser cookie.
    
    Returns:
        Dict with user_id and session_token if cookie exists, None otherwise
    """
    try:
        if 'session_cookie' in st.session_state:
            return st.session_state.session_cookie
    except Exception as e:
        print(f"Failed to get session cookie from state: {e}")
    
    return None


def clear_session_cookie() -> None:
    """Clear session cookie from browser."""
    components.html(JS_DELETE_COOKIE, height=0)
    if 'session_cookie' in st.session_state:
        del st.session_state.session_cookie


def restore_session_from_storage() -> Optional[Dict[str, Any]]:
    """
    Restore user session from browser storage.
    
    This function is called at app startup to check if user has an active
    session cookie and restore it without requiring re-login.
    
    Returns:
        User dict if session is valid, None otherwise
    """
    # Check if we already have session in Streamlit state
    if st.session_state.get('user'):
        return st.session_state.user
    
    # Try to get session from query parameters or hidden state
    # (In production Streamlit, we'd need a custom component for true cookie reading)
    # For now, we use st.experimental_get_query_params as fallback
    try:
        query_params = st.query_params
        if 'session_token' in query_params:
            session_token = query_params['session_token']
            user = sessions.get_user_from_session(session_token)
            if user:
                st.session_state.user = user
                # Renew session if needed
                if sessions.should_renew_session(session_token):
                    new_token = sessions.create_session(user['id'], hours=24)
                    set_session_cookie(user['id'], new_token)
                return user
    except Exception as e:
        print(f"Failed to restore session from storage: {e}")
    
    return None


def login_user(user: Dict[str, Any]) -> None:
    """
    Login user by creating session and setting cookie.
    
    Args:
        user: User dictionary with 'id' and 'email' fields
    """
    try:
        # Create database session (24-hour expiry)
        session_token = sessions.create_session(user['id'], hours=24)
        
        # Set browser cookie (30-day expiry for convenience, but token expires in 24h)
        set_session_cookie(user['id'], session_token, days=30)
        
        # Store in Streamlit session state
        st.session_state.user = user
        st.session_state.session_token = session_token
        
        print(f"User logged in: {user.get('email')} (token: {session_token[:16]}...)")
    except Exception as e:
        print(f"Error during login: {e}")
        raise


def logout_user() -> None:
    """
    Logout user by clearing session and cookie.
    """
    try:
        # Delete session from database
        if 'session_token' in st.session_state:
            try:
                sessions.delete_session(st.session_state.session_token)
            except Exception as e:
                print(f"Failed to delete session from database: {e}")
        
        # Clear browser cookie
        clear_session_cookie()
        
        # Clear Streamlit session state
        st.session_state.user = None
        if 'session_token' in st.session_state:
            del st.session_state.session_token
        
        print("User logged out")
    except Exception as e:
        print(f"Error during logout: {e}")


def restore_session() -> bool:
    """
    Restore user session if available.
    
    Called at app startup. Checks if user has active session in database
    and restores it without requiring re-login.
    
    Returns:
        True if session was restored, False otherwise
    """
    try:
        if st.session_state.get('user'):
            return True
    except Exception as e:
        print(f"Warning: Could not check session state: {e}")
        return False
    
    # Try to get session token from various sources
    session_token = None
    
    # 1. Check if it was stored in previous session state
    try:
        if 'session_token' in st.session_state:
            session_token = st.session_state.session_token
    except Exception as e:
        print(f"Warning: Could not check session token state: {e}")
    
    # 2. Check query parameters (for external redirects)
    if not session_token:
        try:
            query_params = st.query_params
            session_token = query_params.get('token')
        except Exception as e:
            print(f"Warning: Could not check query params: {e}")
    
    if session_token:
        try:
            user = sessions.get_user_from_session(session_token)
            if user:
                st.session_state.user = user
                st.session_state.session_token = session_token
                
                # Auto-renew session if needed (less than 3 hours remaining)
                if sessions.should_renew_session(session_token):
                    new_token = sessions.create_session(user['id'], hours=24)
                    st.session_state.session_token = new_token
                    set_session_cookie(user['id'], new_token)
                
                print(f"Session restored for: {user.get('email')}")
                return True
        except Exception as e:
            print(f"Failed to restore session: {e}")
            # Clear invalid session data
            try:
                st.session_state.user = None
                if 'session_token' in st.session_state:
                    del st.session_state.session_token
            except Exception:
                pass
    
    return False


def is_user_logged_in() -> bool:
    """Check if user is currently logged in."""
    return bool(st.session_state.get('user'))


def get_current_user() -> Optional[Dict[str, Any]]:
    """Get current logged-in user."""
    return st.session_state.get('user')
