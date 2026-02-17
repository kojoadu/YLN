# Cookie-Based Session Management - Quick Start Guide

## For Users

### What This Means
After you register and log in to the YLN mentorship platform, your session will be remembered. You can:
- ✅ Refresh the page without logging in again
- ✅ Close your browser and come back later - you'll stay logged in
- ✅ Access the app across multiple tabs
- ✅ Enjoy uninterrupted access even if the app restarts

### How to Use
1. **Registration**: Create an account with your @mtn.com email
2. **Verification**: Check your email for a 6-digit verification code
3. **Enter Code**: Paste the code to verify your email
4. **Automatic Login**: You'll be automatically logged in after verification
5. **Persistent Session**: Your session will stay active (default 30 days)

### Session Duration
- **Token Validity**: 24 hours from login
- **Cookie Duration**: 30 days in your browser
- **Auto-Renewal**: Session renews automatically when you have less than 3 hours remaining

### Logout
Click the **Logout** button in the sidebar to:
- Clear your session immediately
- Remove the session cookie from your browser
- Return to the login screen

### Troubleshooting

**"I'm logged out when I refresh"**
- Make sure your browser accepts cookies
- Check if you're in private/incognito mode (cookies may be cleared)
- Clear browser cache and try again

**"I see 'Invalid Session' error"**
- Your session token expired (after 24 hours)
- Log in again and you'll get a fresh session
- If problem persists, clear browser cookies and try again

**"I'm on multiple devices"**
- You'll need to log in separately on each device
- Sessions are device-specific (tied to your browser cookies)

---

## For Developers

### Cookie Structure
Cookies are stored with the following attributes:
- **Name**: `yln_session`
- **Duration**: 30 days (configurable)
- **Path**: `/` (site-wide)
- **SameSite**: `Lax` (CSRF protection)
- **Format**: Base64-encoded JSON

### Session Token Flow
```
Login Form
    ↓
authenticate_user() → success
    ↓
login_user(user) → creates session
    ↓
Session Token created in DB (24h expiry)
    ↓
Cookie set in browser (30d expiry)
    ↓
User redirected to app
    ↓
On next page load:
    restore_session() → reads session from state
    → validates token in database
    → restores user automatically
```

### Key Functions (app/cookies.py)

```python
# User logs in
login_user(user: Dict) -> None
  - Creates 24-hour session token in database
  - Sets 30-day cookie in browser
  - Stores user in Streamlit session state

# Restore session on app load
restore_session() -> bool
  - Checks for existing session token
  - Validates with database
  - Auto-renews if < 3 hours remaining
  - Returns True if successful

# User logs out
logout_user() -> None
  - Deletes session token from database
  - Clears cookie from browser
  - Clears Streamlit session state

# Check if user logged in
is_user_logged_in() -> bool
  - Returns True if user in session state

# Get current user
get_current_user() -> Optional[Dict]
  - Returns current user data or None
```

### Integration Points

**In app/main.py:**
```python
# After successful registration + verification
set_user(user)  # Calls login_user()

# On logout button click
logout()  # Calls logout_user()

# On app startup
restore_session_wrapper()  # Calls restore_session()
```

**Session State Variables:**
- `st.session_state.user` - Current user dict
- `st.session_state.session_token` - Current session token

### Database Schema
Sessions stored in `sessions` table:
```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
```

### Configuration
Edit `app/cookies.py` to customize:
- Cookie duration: Change `days` parameter in `set_session_cookie()`
- Token duration: Change `hours` parameter in `login_user()` 
- Session renewal threshold: Change to something other than `should_renew_session()` logic

---

## Security Notes
- Tokens expire after 24 hours, regardless of cookie duration
- Database validation ensures cookies can't be tampered with
- SameSite=Lax prevents CSRF attacks
- All session data cleared on logout
- Sessions tied to user_id, not email (prevents enumeration attacks)
