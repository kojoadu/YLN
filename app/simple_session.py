"""
Improved session management using the approach from the Streamlit documentation.
This uses built-in Streamlit components for better reliability.
"""

import streamlit as st
import streamlit.components.v1 as components
from uuid import uuid4
import time
from app import sessions, db

@st.cache_resource
def get_auth_store():
    """Create a persistent auth store that survives page reloads."""
    return {}

def get_browser_session():
    """Gets or creates a unique session ID stored in a browser cookie."""
    if 'browser_session_id' not in st.session_state:
        # Try to read existing cookie first
        check_cookie_js = """
        <script>
        function getCookie(name) {
            const nameEQ = name + "=";
            const ca = document.cookie.split(';');
            for (let i = 0; i < ca.length; i++) {
                let c = ca[i];
                while (c.charAt(0) === ' ') c = c.substring(1, c.length);
                if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
            }
            return null;
        }
        
        const existingSession = getCookie('yln_browser_session');
        if (existingSession) {
            window.parent.postMessage({
                type: 'streamlit:componentReady',
                sessionId: existingSession
            }, '*');
        } else {
            window.parent.postMessage({
                type: 'streamlit:componentReady', 
                sessionId: null
            }, '*');
        }
        </script>
        """
        
        # Create new session ID
        session_id = uuid4().hex
        st.session_state['browser_session_id'] = session_id
        
        # Set cookie with JavaScript
        set_cookie_js = f"""
        <script>
        function setCookie(name, value, hours) {{
            const date = new Date();
            date.setTime(date.getTime() + (hours * 60 * 60 * 1000));
            const expires = "expires=" + date.toUTCString();
            document.cookie = name + "=" + value + ";" + expires + ";path=/;SameSite=Lax";
            console.log('Session cookie set:', name, value);
        }}
        setCookie('yln_browser_session', '{session_id}', 24); // 24 hour cookie
        </script>
        """
        components.html(set_cookie_js, height=0)
        time.sleep(0.1)  # Small delay to ensure cookie is set
        
    return st.session_state['browser_session_id']

def clear_browser_session():
    """Clear the browser session cookie."""
    clear_cookie_js = """
    <script>
    document.cookie = "yln_browser_session=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    console.log('Session cookie cleared');
    </script>
    """
    components.html(clear_cookie_js, height=0)
    if 'browser_session_id' in st.session_state:
        del st.session_state['browser_session_id']

def restore_user_session():
    """Restore user session using improved cookie approach."""
    session_id = get_browser_session()
    auth_store = get_auth_store()
    
    # Check if this session has a valid user
    if session_id in auth_store:
        user_data = auth_store[session_id]
        if user_data and isinstance(user_data, dict):
            # Verify the user still exists and session is valid
            try:
                # Check if we have a session token
                if 'session_token' in user_data:
                    verified_user = sessions.get_user_from_session(user_data['session_token'])
                    if verified_user:
                        st.session_state.user = verified_user
                        print(f"Session restored from cookie for: {verified_user.get('email', 'Unknown')}")
                        return True
                
                # Fall back to user ID check
                if 'user_id' in user_data:
                    verified_user = db.get_user_by_id(user_data['user_id'])
                    if verified_user:
                        # Create new session token
                        new_token = sessions.create_session(verified_user['id'], hours=1)
                        auth_store[session_id] = {
                            'user_id': verified_user['id'],
                            'session_token': new_token,
                            'email': verified_user['email']
                        }
                        st.session_state.user = verified_user
                        print(f"Session renewed for: {verified_user.get('email', 'Unknown')}")
                        return True
                        
            except Exception as e:
                print(f"Session verification failed: {e}")
                # Clear invalid session
                del auth_store[session_id]
    
    return False

def store_user_session(user):
    """Store user session in the auth store."""
    session_id = get_browser_session()
    auth_store = get_auth_store()
    
    # Create session token
    session_token = sessions.create_session(user['id'], hours=1)
    
    # Store in auth store
    auth_store[session_id] = {
        'user_id': user['id'],
        'session_token': session_token,
        'email': user['email']
    }
    
    st.session_state.user = user
    print(f"User session stored for: {user.get('email', 'Unknown')}")

def clear_user_session():
    """Clear user session from auth store and browser."""
    session_id = get_browser_session() if 'browser_session_id' in st.session_state else None
    auth_store = get_auth_store()
    
    # Clear from auth store
    if session_id and session_id in auth_store:
        user_data = auth_store[session_id]
        # Delete server-side session
        if 'session_token' in user_data:
            try:
                sessions.delete_session(user_data['session_token'])
            except Exception as e:
                print(f"Failed to delete server session: {e}")
        del auth_store[session_id]
    
    # Clear browser cookie
    clear_browser_session()
    
    # Clear session state
    st.session_state.user = None
    print("User session cleared")