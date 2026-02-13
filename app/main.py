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

from streamlit_cookies_manager import CookieManager

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

from app import auth, db
from app import sessions
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
    if "cookies" not in st.session_state:
        st.session_state.cookies = CookieManager()


def restore_session():
    cookies = st.session_state.cookies
    if not cookies.ready():
        return
    session_token = cookies.get("yln_session")
    if session_token and not st.session_state.user:
        user = sessions.get_user_from_session(session_token)
        if user:
            st.session_state.user = user
        else:
            cookies.delete("yln_session")
            cookies.save()


def set_user(user):
    st.session_state.user = user
    st.session_state.mentee_view = "grid"
    st.session_state.selected_mentor_id = None
    token = sessions.create_session(user["id"], days=7)
    cookies = st.session_state.cookies
    if not cookies.ready():
        return
    cookies.set("yln_session", token, max_age=60 * 60 * 24 * 7)
    cookies.save()


def logout():
    cookies = st.session_state.cookies
    if not cookies.ready():
        st.session_state.user = None
        return
    session_token = cookies.get("yln_session")
    if session_token:
        sessions.delete_session(session_token)
    cookies.delete("yln_session")
    cookies.save()
    st.session_state.user = None


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
    st.subheader("Login / Register")
    login_tab, register_tab, verify_tab = st.tabs(["Login", "Register", "Verify Email"])

    with login_tab:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", type="primary"):
            ok, user, msg = auth.authenticate_user(email, password)
            if ok:
                set_user(user)
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with register_tab:
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password", key="reg_password")
        confirm = st.text_input("Confirm Password", type="password", key="reg_confirm")
        if st.button("Register", type="primary"):
            if password != confirm:
                st.error("Passwords do not match.")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                ok, msg, user_id = auth.register_user(email, password)
                if ok and user_id:
                    token = auth.create_verification_token(user_id)
                    send_verification_email(email, token)
                    st.success(msg)
                    st.info("Verification email sent. Check your inbox for the code.")
                else:
                    st.error(msg)

    with verify_tab:
        token = st.text_input("Verification Code")
        if st.button("Verify Email", type="primary"):
            ok, msg = auth.verify_email_token(token)
            if ok:
                st.success(msg)
            else:
                st.error(msg)


def admin_panel():
    st.subheader("Admin: Load Mentors")
    st.info(f"Seeded admin email: {SUPER_ADMIN_EMAIL}")

    with st.form("mentor_form"):
        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("First Name")
            last_name = st.text_input("Last Name")
            phone = st.text_input("Phone Number")
            email = st.text_input("Email Address")
        with col2:
            work_profile = st.text_input("Work Profile")
            profile_pic_url = st.text_input("Profile Pic URL")
            profile_pic_file = st.file_uploader(
                "Upload Profile Pic",
                type=["png", "jpg", "jpeg"],
                key="mentor_profile_pic",
            )
        bio = st.text_area("Bio")

        submitted = st.form_submit_button("Add Mentor", type="primary")
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
    st.subheader("Exports")
    mentors = db.list_mentors()
    mentees = db.list_mentees()
    mentorships = db.list_mentorships()
    pairings = db.list_mentor_pairs()
    export_buffer = io.BytesIO()
    with pd.ExcelWriter(export_buffer, engine="openpyxl") as writer:
        pd.DataFrame(mentors).to_excel(writer, index=False, sheet_name="mentors")
        pd.DataFrame(mentees).to_excel(writer, index=False, sheet_name="mentees")
        pd.DataFrame(mentorships).to_excel(writer, index=False, sheet_name="mentorships")
        pd.DataFrame(pairings).to_excel(writer, index=False, sheet_name="pairings")
    st.download_button(
        "Download all data (XLSX)",
        data=export_buffer.getvalue(),
        file_name="yln_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
        m["id"]: f"{m['first_name']} {m['last_name']}" for m in mentors
    }
    mentee_name_map = {
        m["id"]: f"{m['first_name']} {m['last_name']}" for m in mentees
    }
    mentor_options = [f"{m['id']} - {mentor_name_map[m['id']] }" for m in mentors]
    mentee_options = [f"{m['id']} - {mentee_name_map[m['id']] }" for m in mentees]

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


def mentee_profile_section(user):
    st.subheader("Mentee Profile")
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
                st.success("Profile saved.")


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
        cols = st.columns(3)
        for idx, mentor in enumerate(mentors):
            col = cols[idx % 3]
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
        col1, col2 = st.columns([1, 2])
        with col1:
            if mentor.get("profile_pic"):
                safe_image(mentor["profile_pic"], width=240)
        with col2:
            st.markdown(
                f"**{mentor['first_name']} {mentor['last_name']}**"
            )
            st.write(mentor.get("work_profile") or "")
            st.write(mentor.get("bio") or "")
            st.write(f"Email: {mentor.get('email')}")
            st.write(f"Phone: {mentor.get('phone') or ''}")

        col_a, col_b = st.columns([1, 2])
        with col_a:
            if st.button("Back to mentors"):
                st.session_state.mentee_view = "grid"
                st.session_state.selected_mentor_id = None
                st.rerun()
        with col_b:
            if st.button(
                f"Select {mentor['first_name']} {mentor['last_name']}",
                type="primary",
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
    db.init_db()
    init_state()
    restore_session()
    apply_custom_css()
    header()
    st.divider()

    if not st.session_state.user:
        auth_section()
        return

    user = st.session_state.user
    with st.sidebar:
        st.write(f"Logged in as {user['email']}")
        if user["role"] != Roles.ADMIN:
            page = st.radio(
                "Navigation",
                ["Home", "Profile"],
                index=0,
                key="mentee_nav",
            )
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
        if st.session_state.get("mentee_nav", "Home") == "Profile":
            mentee_profile_section(user)
        else:
            mentorship_section(user)


if __name__ == "__main__":
    main()
