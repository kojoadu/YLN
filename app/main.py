from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_card import card

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import APP_NAME, Roles, SUPER_ADMIN_EMAIL

st.set_page_config(page_title=APP_NAME, page_icon="🤝", layout="wide")

from app.simple_session import (
    restore_user_session,
    store_user_session, 
    clear_user_session
)

UPLOADS_DIR = ROOT_DIR / "app" / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def save_upload(uploaded_file) -> str:
    if not uploaded_file:
        return ""
    safe_name = f"{int(pd.Timestamp.utcnow().timestamp())}_{uploaded_file.name}"
    file_path = UPLOADS_DIR / safe_name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(file_path)


def safe_image(image_ref: str, width: int) -> None:
    if not image_ref:
        return
    cleaned = str(image_ref).strip()
    if (cleaned.startswith("\"") and cleaned.endswith("\"")) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1]
    try:
        st.image(cleaned, width=width)
    except Exception:
        st.warning("Profile image not available.")


def password_reset_request_form():
    """Display password reset request form."""
    st.markdown("### 🔑 Reset Your Password")
    
    with st.form("password_reset_request"):
        st.write("Enter your email address and we'll send you a reset link.")
        email = st.text_input("Email Address")
        submitted = st.form_submit_button("Send Reset Link")
        
        if submitted:
            if not email:
                st.error("Please enter your email address.")
                return
                
            # Validate email domain
            if not email.endswith("@mtn.com"):
                st.error("Please use your @mtn.com email address.")
                return
                
            # Check if user exists
            user = db.get_user_by_email(email)
            if not user:
                # Don't reveal whether email exists for security
                st.success("If an account with that email exists, you'll receive a reset link shortly.")
                return
                
            # Create reset token and send email
            try:
                reset_token = db.create_password_reset_token(user['id'])
                if auth.send_password_reset_email(email, reset_token):
                    st.success("Password reset link sent! Please check your email.")
                else:
                    st.error("Failed to send reset email. Please try again later.")
            except Exception as e:
                st.error("An error occurred. Please try again later.")
                print(f"Password reset error: {e}")


def password_reset_form(token: str):
    """Display password reset form with token validation."""
    # Validate token
    token_data = db.get_password_reset_token(token)
    if not token_data:
        st.error("Invalid or expired reset link. Please request a new password reset.")
        if st.button("Request New Reset Link"):
            st.query_params["page"] = "forgot_password"
            st.rerun()
        return
        
    st.markdown("### 🔑 Set New Password")
    st.write(f"Setting new password for: **{token_data['email']}**")
    
    with st.form("password_reset"):
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Update Password")
        
        if submitted:
            if not new_password or not confirm_password:
                st.error("Please fill in both password fields.")
                return
                
            if new_password != confirm_password:
                st.error("Passwords don't match.")
                return
                
            if len(new_password) < 6:
                st.error("Password must be at least 6 characters long.")
                return
                
            # Update password
            if db.use_password_reset_token(token, new_password):
                st.success("Password updated successfully! You can now sign in with your new password.")
                st.balloons()
                
                # Clear URL parameters and redirect to login after delay
                st.markdown(
                    """
                    <script>
                    setTimeout(function() {
                        window.location.href = window.location.origin;
                    }, 3000);
                    </script>
                    """, 
                    unsafe_allow_html=True
                )
            else:
                st.error("Failed to update password. Please try again.")

from app import auth, db
from app.emailer import (
    send_mentor_assigned_to_mentor,
    send_mentor_assigned_to_mentee,
    send_verification_email,
)


def apply_custom_css() -> None:
    css_path = ROOT_DIR / "app" / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


def init_state() -> None:
    if "user" not in st.session_state:
        st.session_state.user = None
    if "mentee_view" not in st.session_state:
        st.session_state.mentee_view = "grid"
    if "selected_mentor_id" not in st.session_state:
        st.session_state.selected_mentor_id = None


def restore_session():
    """Restore user session using improved cookie approach."""
    if not st.session_state.user:
        restore_user_session()


def set_user(user):
    store_user_session(user)


def logout():
    clear_user_session()


def header():
    st.markdown(
        f"""
        <div class="yln-header">
            <div class="yln-header__title">{APP_NAME}</div>
            <div class="yln-header__subtitle">Be more. With a mentor who’s been there.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def auth_section():
    query_params = st.query_params
    
    # Handle password reset request page
    if query_params.get("page") == "forgot_password":
        password_reset_request_form()
        if st.button("← Back to Login"):
            st.query_params.clear()
            st.rerun()
        return
    
    # Handle password reset form with token
    if query_params.get("page") == "reset_password" and "token" in query_params:
        password_reset_form(query_params["token"])
        if st.button("← Back to Login"):
            st.query_params.clear()
            st.rerun()
        return
    
    # Handle email verification
    if "token" in query_params and "page" not in query_params:
        token = query_params["token"]
        ok, msg = auth.verify_email_token(token)
        if ok:
            st.success(f"✅ {msg}")
            st.balloons()
        else:
            st.error(f"❌ {msg}")
        
        if st.button("Continue to Login"):
            st.query_params.clear()
            st.rerun()
        return
    
    # Check if user just registered and needs to verify email
    if 'pending_verification' in st.session_state:
        st.markdown("### 📧 Check Your Email")
        
        user_email = st.session_state.pending_verification['email']
        user_id = st.session_state.pending_verification['user_id']
        
        st.success("Account created successfully!")
        st.info(f"A verification email has been sent to **{user_email}**")
        st.write("Please check your inbox and enter the verification code below:")
        
        with st.form("email_verification"):
            token = st.text_input("Verification Code", placeholder="Enter 6-digit code from email")
            
            # Mobile-optimized button layout
            if st.form_submit_button("✅ Verify Email", type="primary", use_container_width=True):
                if not token:
                    st.error("Please enter the verification code.")
                else:
                    ok, msg = auth.verify_email_token(token)
                    if ok:
                        st.success(msg)
                        del st.session_state.pending_verification
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)
            
            if st.form_submit_button("📧 Resend Email", use_container_width=True):
                try:
                    new_token = auth.create_verification_token(user_id)
                    if send_verification_email(user_email, new_token):
                        st.success("Verification email resent!")
                    else:
                        st.error("Failed to resend email.")
                except Exception as e:
                    st.error("Error resending email.")
        
        # Back button
        if st.button("← Back to Registration", use_container_width=True):
            del st.session_state.pending_verification
            st.rerun()
        return
    
    st.subheader("Login / Register")
    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        email = st.text_input("Email", key="login_email", placeholder="your.email@mtn.com")
        password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
        
        # Mobile-optimized button layout
        if st.button("🔓 Login", type="primary", use_container_width=True):
            ok, user, msg = auth.authenticate_user(email, password)
            if ok:
                set_user(user)
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
        
        # Forgot password as a smaller secondary button
        if st.button("🔑 Forgot Password?", use_container_width=True):
            st.query_params["page"] = "forgot_password"
            st.rerun()

    with register_tab:
        email = st.text_input("Email", key="reg_email", placeholder="your.email@mtn.com")
        password = st.text_input("Password", type="password", key="reg_password", placeholder="Minimum 6 characters")
        confirm = st.text_input("Confirm Password", type="password", key="reg_confirm", placeholder="Confirm your password")
        if st.button("📝 Create Account", type="primary", use_container_width=True):
            if password != confirm:
                st.error("Passwords do not match.")
            elif not email or not email.strip().lower().endswith("@mtn.com"):
                st.error("Email must be an @mtn.com address.")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                ok, msg, user_id = auth.register_user(email, password)
                if ok and user_id:
                    token = auth.create_verification_token(user_id)
                    if send_verification_email(email, token):
                        # Set verification pending state
                        st.session_state.pending_verification = {
                            'email': email,
                            'user_id': user_id
                        }
                        st.rerun()
                    else:
                        st.warning("Account created but failed to send verification email.")
                else:
                    st.error(msg)


def admin_panel():
    st.subheader("Admin Panel")
    
    # Google Sheets Status Section
    st.subheader("Google Sheets Integration")
    from app.config import SHEETS_ENABLED, SHEETS_SPREADSHEET_ID
    
    if SHEETS_ENABLED:
        st.success("✅ Google Sheets integration is enabled")
        if SHEETS_SPREADSHEET_ID:
            st.info(f"📊 Spreadsheet ID: {SHEETS_SPREADSHEET_ID}")
        
        # Show pending writes count
        with db.get_conn() as conn:
            pending_count = conn.execute(
                "SELECT COUNT(*) as count FROM pending_sheets_writes WHERE status = 'pending'"
            ).fetchone()['count']
            failed_count = conn.execute(
                "SELECT COUNT(*) as count FROM pending_sheets_writes WHERE status = 'failed'"
            ).fetchone()['count']
        
        # Mobile-responsive metrics
        st.subheader("Sync Status")
        
        # Stack metrics vertically on mobile for better readability
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            st.metric("Pending", pending_count)
        with col2:
            st.metric("Failed", failed_count)
        with col3:
            if st.button("🔄 Retry", use_container_width=True, help="Retry failed writes"):
                try:
                    db.process_pending_sheets_writes()
                    st.success("Retry completed!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Retry failed: {e}")
        
        # Sync functionality with mobile-optimized layout
        st.subheader("🔄 Database Sync")
        
        # Import the configuration to check database mode
        from app.config import USE_SHEETS_ONLY, USE_SQLITE
        
        if USE_SHEETS_ONLY:
            st.caption("📊 Using Google Sheets as primary storage")
            st.info("**Mode:** Sheets-Only Mode (SQLite disabled)")
        else:
            st.caption("Sync SQLite data with Google Sheets")
            
        # Only show sync button if we're not in sheets-only mode
        if not USE_SHEETS_ONLY:
            # Full-width buttons for mobile
            if st.button("📊 Full Sync to Sheets", type="primary", use_container_width=True, help="Sync all data to Google Sheets"):
                with st.spinner("Syncing data to Google Sheets..."):
                    result = db.sync_all_to_sheets()
                    
                if result['success']:
                    st.success("✅ Sync completed!")
                    
                    # Show detailed results in compact format
                    results = result['results']
                    for entity, stats in results.items():
                        synced = stats['synced']
                        errors = stats['errors']
                        if synced > 0 or errors > 0:
                            st.info(f"**{entity.title()}:** {synced} synced, {errors} errors")
                else:
                    st.error(f"❌ Sync failed: {result.get('message', 'Unknown error')}")
        else:
            st.success("✅ All data operations are now directly using Google Sheets")
        
        # Clear sheets section with mobile optimization
        st.write("")
        with st.expander("🗑️ Clear Sheets Data", expanded=False):
            st.warning("⚠️ This will clear ALL Google Sheets data (except headers)")
            
            if st.button("🗑️ Clear All Sheets Data", use_container_width=True):
                if st.checkbox("✅ I understand this will clear all data", key="clear_confirm"):
                    with st.spinner("Clearing Google Sheets data..."):
                        entities = ['users', 'mentors', 'mentees', 'mentorships', 'sessions']
                        cleared_count = 0
                        
                        for entity in entities:
                            if db.clear_sheets_data(entity):
                                cleared_count += 1
                        
                        if cleared_count == len(entities):
                            st.success(f"✅ Cleared data from {cleared_count} worksheets")
                        else:
                            st.warning(f"⚠️ Cleared {cleared_count}/{len(entities)} worksheets")
                else:
                    st.info("Please confirm to proceed")
    else:
        st.warning("⚠️ Google Sheets integration is disabled")
    
    st.divider()
    st.subheader("👥 Users Management")
    
    # Initialize session state for user management
    if 'selected_user_for_edit' not in st.session_state:
        st.session_state.selected_user_for_edit = None
    if 'show_user_form' not in st.session_state:
        st.session_state.show_user_form = False
    
    # Desktop vs Mobile Layout
    users = db.list_users()
    
    if users:
        # Display metrics
        total_users = len(users)
        verified_users = len([u for u in users if u.get('is_verified', False)])
        admin_users = len([u for u in users if u.get('role') == 'admin'])
        
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        with col1:
            st.metric("Total Users", total_users)
        with col2:
            st.metric("Verified", verified_users)
        with col3:
            st.metric("Admins", admin_users)
        with col4:
            if st.button("➕ Add New User", type="primary", use_container_width=True):
                st.session_state.show_user_form = True
                st.session_state.selected_user_for_edit = None
                st.rerun()
        
        # Search and filter
        st.write("")
        search_col, filter_col = st.columns([2, 1])
        with search_col:
            search_term = st.text_input("🔍 Search users by email", placeholder="Enter email to search...")
        with filter_col:
            role_filter = st.selectbox("Filter by role", ["All", "admin", "user"], index=0)
        
        # Filter users based on search and role
        filtered_users = users
        if search_term:
            filtered_users = [u for u in filtered_users if search_term.lower() in u.get('email', '').lower()]
        if role_filter != "All":
            filtered_users = [u for u in filtered_users if u.get('role', '') == role_filter]
        
        # Desktop view with action buttons
        st.write("")
        
        # Create enhanced table with actions
        if filtered_users:
            for idx, user in enumerate(filtered_users):
                with st.container():
                    user_col, status_col, role_col, created_col, actions_col = st.columns([3, 1, 1, 2, 2])
                    
                    with user_col:
                        st.write(f"**{user['email']}**")
                        st.caption(f"ID: {user['id']}")
                    
                    with status_col:
                        status = "✅ Verified" if user.get('is_verified') else "❌ Unverified"
                        st.write(status)
                    
                    with role_col:
                        st.write(user.get('role', 'user').title())
                    
                    with created_col:
                        if user.get('created_at'):
                            created_date = pd.to_datetime(user['created_at']).strftime('%Y-%m-%d %H:%M')
                            st.write(created_date)
                    
                    with actions_col:
                        action_col1, action_col2, action_col3 = st.columns(3)
                        
                        with action_col1:
                            if st.button("✏️", key=f"edit_{user['id']}_{idx}", help="Edit user"):
                                st.session_state.selected_user_for_edit = user['id']
                                st.session_state.show_user_form = True
                                st.rerun()
                        
                        with action_col2:
                            verify_label = "❌" if user.get('is_verified') else "✅"
                            verify_help = "Unverify user" if user.get('is_verified') else "Verify user"
                            if st.button(verify_label, key=f"verify_{user['id']}_{idx}", help=verify_help):
                                if db.toggle_user_verification(user['id']):
                                    st.success(f"User verification status updated!")
                                    st.rerun()
                                else:
                                    st.error("Failed to update verification status")
                        
                        with action_col3:
                            if user.get('role') != 'admin' or len([u for u in users if u.get('role') == 'admin']) > 1:
                                if st.button("🗑️", key=f"delete_{user['id']}_{idx}", help="Delete user"):
                                    if st.session_state.get(f"confirm_delete_{user['id']}_{idx}", False):
                                        if db.delete_user(user['id']):
                                            st.success(f"User {user['email']} deleted successfully!")
                                            st.rerun()
                                        else:
                                            st.error("Failed to delete user")
                                    else:
                                        st.session_state[f"confirm_delete_{user['id']}_{idx}"] = True
                                        st.warning(f"⚠️ Click delete again to confirm removal of {user['email']}")
                    
                    # Add confirmation reset
                    if st.session_state.get(f"confirm_delete_{user['id']}_{idx}", False):
                        if st.button(f"Cancel deletion of {user['email']}", key=f"cancel_delete_{user['id']}_{idx}"):
                            st.session_state[f"confirm_delete_{user['id']}_{idx}"] = False
                            st.rerun()
                    
                    st.divider()
        else:
            st.info("No users match the current filters.")
        
        # Export options
        st.write("**📊 Export Options:**")
        col1, col2 = st.columns(2)
        with col1:
            users_df = pd.DataFrame(filtered_users)
            if 'created_at' in users_df.columns:
                users_df['created_at'] = pd.to_datetime(users_df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
            if 'is_verified' in users_df.columns:
                users_df['is_verified'] = users_df['is_verified'].map({1: 'Verified', 0: 'Unverified', True: 'Verified', False: 'Unverified'})
            
            st.download_button(
                "📄 Download Filtered Users (CSV)",
                data=users_df.to_csv(index=False),
                file_name="yln_users_filtered.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col2:
            users_xlsx = io.BytesIO()
            users_df.to_excel(users_xlsx, index=False, engine='openpyxl')
            st.download_button(
                "📊 Download Filtered Users (XLSX)",
                data=users_xlsx.getvalue(),
                file_name="yln_users_filtered.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    else:
        st.info("No users found in the system.")
        if st.button("➕ Add First User", type="primary", use_container_width=True):
            st.session_state.show_user_form = True
            st.session_state.selected_user_for_edit = None
            st.rerun()
    
    # User Creation/Edit Form
    if st.session_state.show_user_form:
        st.write("")
        edit_user = None
        if st.session_state.selected_user_for_edit:
            edit_user = db.get_user_by_id(st.session_state.selected_user_for_edit)
        
        form_title = "✏️ Edit User" if edit_user else "➕ Add New User"
        st.subheader(form_title)
        
        with st.form("user_management_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                email = st.text_input(
                    "Email Address",
                    value=edit_user.get('email', '') if edit_user else '',
                    placeholder="user@mtn.com",
                    disabled=bool(edit_user)  # Can't change email for existing users
                )
            
            with col2:
                role = st.selectbox(
                    "Role",
                    ["user", "admin"],
                    index=1 if (edit_user and edit_user.get('role') == 'admin') else 0
                )
            
            if not edit_user:
                password = st.text_input("Password", type="password", placeholder="Minimum 6 characters")
                confirm_password = st.text_input("Confirm Password", type="password")
            
            verified = st.checkbox(
                "Email Verified",
                value=bool(edit_user.get('is_verified', False)) if edit_user else True
            )
            
            submit_col1, submit_col2 = st.columns([1, 1])
            
            with submit_col1:
                if st.form_submit_button("💾 Save User", type="primary", use_container_width=True):
                    if edit_user:
                        # Update existing user
                        success = True
                        if db.update_user_role(edit_user['id'], role):
                            if verified != bool(edit_user.get('is_verified', False)):
                                success = db.toggle_user_verification(edit_user['id'])
                            if success:
                                st.success(f"User {email} updated successfully!")
                                st.session_state.show_user_form = False
                                st.session_state.selected_user_for_edit = None
                                st.rerun()
                            else:
                                st.error("Failed to update user verification status")
                        else:
                            st.error("Failed to update user role")
                    else:
                        # Create new user
                        if not email or not email.endswith('@mtn.com'):
                            st.error("Email must be an @mtn.com address.")
                        elif not password or len(password) < 6:
                            st.error("Password must be at least 6 characters.")
                        elif password != confirm_password:
                            st.error("Passwords do not match.")
                        else:
                            from app.security import hash_password
                            password_hash = hash_password(password)
                            user_id = db.create_user(email, password_hash, role)
                            if user_id:
                                if verified:
                                    db.set_user_verified(user_id)
                                st.success(f"User {email} created successfully!")
                                st.session_state.show_user_form = False
                                st.rerun()
                            else:
                                st.error("Failed to create user. Email may already exist.")
            
            with submit_col2:
                if st.form_submit_button("❌ Cancel", use_container_width=True):
                    st.session_state.show_user_form = False
                    st.session_state.selected_user_for_edit = None
                    st.rerun()
    
    st.divider()
    st.subheader("➕ Add Mentors")
    st.caption(f"Admin: {SUPER_ADMIN_EMAIL}")

    with st.form("mentor_form"):
        # Mobile-optimized form layout
        first_name = st.text_input("First Name", placeholder="Enter first name")
        last_name = st.text_input("Last Name", placeholder="Enter last name")
        phone = st.text_input("Phone Number", placeholder="Optional contact number")
        email = st.text_input("Email Address", placeholder="mentor@mtn.com")
        work_profile = st.text_input("Work Profile", placeholder="Job title or expertise area")
        bio = st.text_area("Bio", placeholder="Brief description about the mentor...")
        
        # Profile picture options in expandable section
        with st.expander("📸 Profile Picture (Optional)", expanded=False):
            profile_pic_url = st.text_input("Profile Pic URL", placeholder="https://example.com/image.jpg")
            st.write("**OR**")
            profile_pic_file = st.file_uploader(
                "Upload Profile Pic",
                type=["png", "jpg", "jpeg"],
                key="mentor_profile_pic",
                help="Max file size: 5MB"
            )

        submitted = st.form_submit_button("➕ Add Mentor", type="primary", use_container_width=True)
        if submitted:
            if not first_name or not last_name or not email:
                st.error("First name, last name, and email are required.")
            else:
                profile_pic = profile_pic_url
                if profile_pic_file is not None:
                    profile_pic = save_upload(profile_pic_file)
                db.create_mentor(
                    {
                        "first_name": first_name,
                        "last_name": last_name,
                        "phone": phone,
                        "email": email,
                        "work_profile": work_profile,
                        "bio": bio,
                        "profile_pic": profile_pic,
                    }
                )
                st.success("Mentor added.")

    st.divider()
    st.subheader("📊 Exports")
    users = db.list_users()
    mentors = db.list_mentors()
    mentees = db.list_mentees()
    mentorships = db.list_mentorships()
    pairings = db.list_mentor_pairs()
    export_buffer = io.BytesIO()
    with pd.ExcelWriter(export_buffer, engine="openpyxl") as writer:
        pd.DataFrame(users).to_excel(writer, index=False, sheet_name="users")
        pd.DataFrame(mentors).to_excel(writer, index=False, sheet_name="mentors")
        pd.DataFrame(mentees).to_excel(writer, index=False, sheet_name="mentees")
        pd.DataFrame(mentorships).to_excel(writer, index=False, sheet_name="mentorships")
        pd.DataFrame(pairings).to_excel(writer, index=False, sheet_name="pairings")
    st.download_button(
        "📥 Download all data (XLSX)",
        data=export_buffer.getvalue(),
        file_name="yln_complete_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        help="Downloads all system data including users, mentors, mentees, mentorships, and pairings"
    )

    st.divider()
    st.subheader("Mentor Pairings")
    pairs = pairings
    if pairs:
        pairs_df = pd.DataFrame(pairs)
        st.download_button(
            "Download mentor pairings (CSV)",
            data=pairs_df.to_csv(index=False),
            file_name="mentor_pairings.csv",
            mime="text/csv",
        )
        pairs_xlsx = io.BytesIO()
        pairs_df.to_excel(pairs_xlsx, index=False)
        st.download_button(
            "Download mentor pairings (XLSX)",
            data=pairs_xlsx.getvalue(),
            file_name="mentor_pairings.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.dataframe(pairs_df, use_container_width=True)
    else:
        st.info("No mentors found.")

    st.subheader("Mentorships (Edit/Delete)")
    mentorships = mentorships
    mentors = mentors
    mentees = mentees
    mentor_name_map = {
        m["id"]: f"{m.get('first_name', '')} {m.get('last_name', '')}" for m in mentors if m.get("id")
    }
    mentee_name_map = {
        m["id"]: f"{m.get('first_name', '')} {m.get('last_name', '')}" for m in mentees if m.get("id")
    }
    mentor_options = [f"{m['id']} - {mentor_name_map.get(m['id'], 'Unknown')}" for m in mentors if m.get("id")]
    mentee_options = [f"{m['id']} - {mentee_name_map.get(m['id'], 'Unknown')}" for m in mentees if m.get("id")]

    def _choice_to_id(choice: str) -> int:
        return int(str(choice).split("-", 1)[0].strip())
    if mentorships:
        ms_df = pd.DataFrame(mentorships)
        st.download_button(
            "Download mentorships (CSV)",
            data=ms_df.to_csv(index=False),
            file_name="mentorships.csv",
            mime="text/csv",
        )
        ms_xlsx = io.BytesIO()
        ms_df.to_excel(ms_xlsx, index=False)
        st.download_button(
            "Download mentorships (XLSX)",
            data=ms_xlsx.getvalue(),
            file_name="mentorships.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        ms_df.insert(0, "delete", False)
        ms_df["mentor_name"] = ms_df["mentor_id"].map(mentor_name_map)
        ms_df["mentee_name"] = ms_df["mentee_id"].map(mentee_name_map)
        ms_df["mentor_choice"] = ms_df.apply(
            lambda r: f"{r['mentor_id']} - {mentor_name_map.get(r['mentor_id'], '')}",
            axis=1,
        )
        ms_df["mentee_choice"] = ms_df.apply(
            lambda r: f"{r['mentee_id']} - {mentee_name_map.get(r['mentee_id'], '')}",
            axis=1,
        )
        edited_ms = st.data_editor(
            ms_df,
            use_container_width=True,
            key="mentorship_editor",
            disabled=[
                "id",
                "created_at",
                "mentor_name",
                "mentee_name",
                "mentor_id",
                "mentee_id",
            ],
            column_order=[
                "delete",
                "id",
                "mentor_id",
                "mentor_name",
                "mentee_id",
                "mentee_name",
                "mentor_choice",
                "mentee_choice",
                "created_at",
            ],
            column_config={
                "delete": st.column_config.CheckboxColumn("Delete", default=False),
                "mentor_id": st.column_config.NumberColumn("Mentor ID"),
                "mentee_id": st.column_config.NumberColumn("Mentee ID"),
                "mentor_name": st.column_config.TextColumn("Mentor Name"),
                "mentee_name": st.column_config.TextColumn("Mentee Name"),
                "mentor_choice": st.column_config.SelectboxColumn(
                    "Mentor",
                    options=mentor_options,
                ),
                "mentee_choice": st.column_config.SelectboxColumn(
                    "Mentee",
                    options=mentee_options,
                ),
            },
        )
        if st.button("Apply mentorship changes", type="primary"):
            original = {m["id"]: m for m in mentorships}
            errors = []
            for _, row in edited_ms.iterrows():
                ms_id = int(row["id"])
                if bool(row["delete"]):
                    db.delete_mentorship(ms_id)
                    continue
                new_mentor_id = _choice_to_id(row["mentor_choice"])
                new_mentee_id = _choice_to_id(row["mentee_choice"])
                if (
                    new_mentor_id != original[ms_id]["mentor_id"]
                    or new_mentee_id != original[ms_id]["mentee_id"]
                ):
                    ok, msg = db.update_mentorship(ms_id, new_mentor_id, new_mentee_id)
                    if not ok:
                        errors.append(f"{msg} (mentorship {ms_id})")
            if errors:
                for err in errors:
                    st.error(err)
            else:
                st.success("Mentorship updates applied.")
                st.rerun()
    else:
        st.info("No mentorships found.")

    st.divider()
    st.subheader("Mentors Table (Edit/Delete)")
    mentors = db.list_mentors()
    if mentors:
        mentor_df = pd.DataFrame(mentors)
        st.download_button(
            "Download mentors (CSV)",
            data=mentor_df.to_csv(index=False),
            file_name="mentors.csv",
            mime="text/csv",
        )
        mentors_xlsx = io.BytesIO()
        mentor_df.to_excel(mentors_xlsx, index=False)
        st.download_button(
            "Download mentors (XLSX)",
            data=mentors_xlsx.getvalue(),
            file_name="mentors.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        mentor_df.insert(0, "delete", False)
        edited_mentors = st.data_editor(
            mentor_df,
            use_container_width=True,
            key="mentor_editor",
            disabled=["id", "created_at"],
            column_config={
                "delete": st.column_config.CheckboxColumn("Delete", default=False),
                "is_active": st.column_config.CheckboxColumn("Active", default=True),
            },
        )
        if st.button("Apply mentor changes", type="primary"):
            for _, row in edited_mentors.iterrows():
                mentor_id = int(row["id"])
                if bool(row["delete"]):
                    db.delete_mentor(mentor_id)
                    continue
                db.update_mentor(
                    mentor_id,
                    {
                        "first_name": row.get("first_name"),
                        "last_name": row.get("last_name"),
                        "phone": row.get("phone"),
                        "email": row.get("email"),
                        "work_profile": row.get("work_profile"),
                        "bio": row.get("bio"),
                        "profile_pic": row.get("profile_pic"),
                        "is_active": int(bool(row.get("is_active", 1))),
                    },
                )
            st.success("Mentor updates applied.")
            st.rerun()
    else:
        st.info("No mentors found.")

    st.subheader("Mentees Table (Edit/Delete)")
    mentees = db.list_mentees()
    if mentees:
        mentee_df = pd.DataFrame(mentees)
        st.download_button(
            "Download mentees (CSV)",
            data=mentee_df.to_csv(index=False),
            file_name="mentees.csv",
            mime="text/csv",
        )
        mentees_xlsx = io.BytesIO()
        mentee_df.to_excel(mentees_xlsx, index=False)
        st.download_button(
            "Download mentees (XLSX)",
            data=mentees_xlsx.getvalue(),
            file_name="mentees.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        mentee_df.insert(0, "delete", False)
        edited_mentees = st.data_editor(
            mentee_df,
            use_container_width=True,
            key="mentee_editor",
            disabled=["id", "user_id", "created_at"],
            column_config={
                "delete": st.column_config.CheckboxColumn("Delete", default=False),
            },
        )
        if st.button("Apply mentee changes", type="primary"):
            for _, row in edited_mentees.iterrows():
                mentee_id = int(row["id"])
                if bool(row["delete"]):
                    db.delete_mentee(mentee_id)
                    continue
                db.update_mentee(
                    mentee_id,
                    {
                        "first_name": row.get("first_name"),
                        "last_name": row.get("last_name"),
                        "phone": row.get("phone"),
                        "email": row.get("email"),
                        "work_profile": row.get("work_profile"),
                        "profile_pic": row.get("profile_pic"),
                    },
                )
            st.success("Mentee updates applied.")
            st.rerun()
    else:
        st.info("No mentees found.")


def is_mentee_profile_complete(user_id: int) -> bool:
    """Check if mentee profile has required fields completed."""
    mentee_profile = db.get_mentee_by_user_id(user_id)
    if not mentee_profile:
        return False
    
    # Check for required fields
    required_fields = ["first_name", "last_name", "email"]
    return all(mentee_profile.get(field) for field in required_fields)


def mentee_profile_section(user):
    st.subheader("👤 Mentee Profile")
    
    # Check if this is a required completion
    profile_complete = is_mentee_profile_complete(user["id"])
    if not profile_complete:
        st.info("📝 Please complete your profile to access mentor matching and other features.")
    
    profile = db.get_mentee_by_user_id(user["id"]) or {}
    with st.form("mentee_profile"):
        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("First Name", value=profile.get("first_name", ""))
            last_name = st.text_input("Last Name", value=profile.get("last_name", ""))
            phone = st.text_input("Phone Number", value=profile.get("phone", ""))
            email = st.text_input("Email Address", value=profile.get("email", user["email"]))
        with col2:
            work_profile = st.text_input("Work Profile", value=profile.get("work_profile", ""))
            profile_pic_url = st.text_input(
                "Profile Pic URL",
                value=profile.get("profile_pic", ""),
            )
            profile_pic_file = st.file_uploader(
                "Upload Profile Pic",
                type=["png", "jpg", "jpeg"],
                key="mentee_profile_pic",
            )

        submitted = st.form_submit_button("Save Profile", type="primary")
        if submitted:
            if not first_name or not last_name:
                st.error("First name and last name are required.")
            else:
                profile_pic = profile_pic_url
                if profile_pic_file is not None:
                    profile_pic = save_upload(profile_pic_file)
                db.create_or_update_mentee_profile(
                    user["id"],
                    {
                        "first_name": first_name,
                        "last_name": last_name,
                        "phone": phone,
                        "email": email,
                        "work_profile": work_profile,
                        "profile_pic": profile_pic,
                    },
                )
                st.success("✅ Profile saved successfully! You can now access all features.")
                # Update session state to allow navigation to Home
                st.session_state["mentee_nav"] = "Home"
                st.rerun()


def mentorship_section(user):
    st.subheader("Select a Mentor")
    mentee = db.get_mentee_by_user_id(user["id"])
    if not mentee:
        st.warning("Please complete your mentee profile first.")
        return

    existing = db.get_mentorship_by_mentee(mentee["id"])
    if existing:
        mentor = db.get_mentor(existing["mentor_id"])
        if mentor:
            st.success(
                f"You already have a mentor: {mentor['first_name']} {mentor['last_name']}"
            )
        return

    mentors = db.list_available_mentors()
    if not mentors:
        st.info("No mentors available at the moment.")
        return

    if st.session_state.mentee_view == "grid":
        st.caption("Browse mentors and open a profile to select.")
        
        # Responsive columns based on screen size
        # Mobile: 1 column, Tablet: 2 columns, Desktop: 3 columns
        num_cols = 1 if len(mentors) < 3 else 3
        cols = st.columns(num_cols)
        
        for idx, mentor in enumerate(mentors):
            col_idx = idx % num_cols
            col = cols[col_idx]
            with col:
                # Create card content
                card_text = f"""
                **{mentor['first_name']} {mentor['last_name']}**
                
                {mentor.get('work_profile') or ''}
                
                {(mentor.get('bio') or '')[:140]}...
                """
                
                # Create card with click functionality
                hasClicked = card(
                    title=f"{mentor['first_name']} {mentor['last_name']}",
                    text=f"{mentor.get('work_profile') or ''}",
                    image=mentor.get('profile_pic', ''),
                    key=f"card_{mentor['id']}"
                )
                
                if hasClicked:
                    st.session_state.selected_mentor_id = mentor["id"]
                    st.session_state.mentee_view = "profile"
                    st.rerun()

    if st.session_state.mentee_view == "profile":
        mentor = db.get_mentor(st.session_state.selected_mentor_id)
        if not mentor:
            st.session_state.mentee_view = "grid"
            st.rerun()
            return

        st.subheader("Mentor Profile")
        
        # Mobile-first responsive layout
        # Stack everything vertically on mobile, side-by-side on larger screens
        if mentor.get("profile_pic"):
            # Center the image on mobile
            col_img = st.columns([1, 2, 1])[1]  # Center column
            with col_img:
                safe_image(mentor["profile_pic"], width=200)
            st.write("")  # Add some space
        
        # Profile information
        st.markdown(f"### {mentor['first_name']} {mentor['last_name']}")
        if mentor.get("work_profile"):
            st.markdown(f"**{mentor.get('work_profile')}**")
        if mentor.get("bio"):
            st.markdown(f"*{mentor.get('bio')}*")
        
        # Contact info in expandable section for cleaner mobile view
        with st.expander("📧 Contact Information", expanded=False):
            st.write(f"**Email:** {mentor.get('email')}")
            if mentor.get('phone'):
                st.write(f"**Phone:** {mentor.get('phone')}")

        # Action buttons - stack vertically on mobile
        st.write("")
        col_back, col_select = st.columns([1, 2])
        with col_back:
            if st.button("← Back to mentors", use_container_width=True):
                st.session_state.mentee_view = "grid"
                st.session_state.selected_mentor_id = None
                st.rerun()
        with col_select:
            if st.button(
                f"✅ Select {mentor['first_name']} {mentor['last_name']}",
                type="primary",
                use_container_width=True,
            ):
                ok, msg = db.assign_mentor(mentee["id"], mentor["id"])
                if ok:
                    mentor_name = f"{mentor['first_name']} {mentor['last_name']}"
                    mentee_name = f"{mentee['first_name']} {mentee['last_name']}"
                    send_mentor_assigned_to_mentor(
                        mentor["email"], mentor_name, mentee_name
                    )
                    send_mentor_assigned_to_mentee(
                        mentee["email"], mentee_name, mentor_name
                    )
                    st.success("Mentor assigned successfully.")
                    st.session_state.mentee_view = "grid"
                    st.session_state.selected_mentor_id = None
                    st.rerun()
                else:
                    st.error(msg)


def main():
    try:
        db.init_db()
        print("Database initialized successfully")
        
        # Verify super admin exists
        from app.config import SUPER_ADMIN_EMAIL
        admin_user = db.get_user_by_email(SUPER_ADMIN_EMAIL)
        if admin_user:
            print(f"Super admin verified: {SUPER_ADMIN_EMAIL}")
        else:
            print(f"Super admin not found, re-seeding: {SUPER_ADMIN_EMAIL}")
            db.seed_super_admin()
            
    except Exception as e:
        print(f"Database initialization error: {e}")
        st.error("Database initialization failed. Please contact support.")
        return
    init_state()
    restore_session()
    apply_custom_css()
    
    # Process pending sheets writes on app startup
    try:
        db.process_pending_sheets_writes()
    except Exception as e:
        # Don't let sheets processing break the app
        print(f"Failed to process pending sheets writes: {e}")
    
    header()
    st.divider()

    if not st.session_state.user:
        auth_section()
        return

    user = st.session_state.user
    
    # Initialize navigation state before creating widgets
    if user and user["role"] != Roles.ADMIN:
        profile_complete = is_mentee_profile_complete(user["id"])
        
        # Set default navigation state
        if "mentee_nav" not in st.session_state:
            # Default to Profile if incomplete, Home if complete
            st.session_state["mentee_nav"] = 1 if not profile_complete else 0
    
    with st.sidebar:
        st.write(f"Logged in as {user['email']}")
        if user["role"] != Roles.ADMIN:
            # Check profile completion status for navigation
            profile_complete = is_mentee_profile_complete(user["id"])
            
            # Navigation options with indicators
            nav_options = [
                "Home" if profile_complete else "🔒 Home (Complete Profile First)",
                "👤 Profile" + ("" if profile_complete else " ⚠️")
            ]
            
            # Use the pre-set session state index
            selected_index = st.radio(
                "Navigation",
                options=range(len(nav_options)),
                format_func=lambda i: nav_options[i],
                index=st.session_state.get("mentee_nav", 0),
                key="mentee_nav",
            )
            
            # Determine current page based on selected index
            current_page = "Profile" if selected_index == 1 else "Home"
            
        if st.button("Logout"):
            logout()
            st.rerun()

    if user["role"] == Roles.ADMIN:
        admin_panel()
    else:
        mentee_profile = db.get_mentee_by_user_id(user["id"]) if user else None
        first_name = (
            mentee_profile.get("first_name") if mentee_profile else None
        )
        greeting_name = first_name or user["email"]
        
        st.markdown(
            f"""
            <div class="yln-welcome">
                <div class="yln-welcome__title">Welcome, {greeting_name}</div>
                <div class="yln-welcome__subtitle">Connect your talent with tenured expertise.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()
        
        if current_page == "Profile":
            mentee_profile_section(user)
        else:
            mentorship_section(user)


if __name__ == "__main__":
    main()
