# utils.py
import streamlit as st
import hmac
import time
import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import config
import numpy as np # Keep if used elsewhere, not strictly needed in utils now

# --- Password Check (Keep as is) ---
def check_password():
    """Returns 'True' if the user has entered a correct password."""
    def login_form():
        with st.form("Credentials"):
            st.text_input("Username", key="username"); st.text_input("Password", type="password", key="password")
            st.form_submit_button("Log in", on_click=password_entered)
    def password_entered():
        if "passwords" in st.secrets and st.session_state.username in st.secrets.passwords:
             expected_password_or_hash = st.secrets.passwords[st.session_state.username]
             if "password" in st.session_state and st.session_state.password == expected_password_or_hash: st.session_state.password_correct = True
             # Add HMAC logic here if needed based on secrets format
             else: st.session_state.password_correct = False
        else: st.session_state.password_correct = False
        if "password" in st.session_state: del st.session_state.password
    current_username = st.session_state.get("username", None)
    if st.session_state.get("password_correct", False): return True, current_username
    login_form(); submitted_username = st.session_state.get("username", None)
    if "password_correct" in st.session_state and not st.session_state.password_correct: st.error("User or password incorrect")
    return False, submitted_username

# --- Interview Check (Keep as is) ---
def check_if_interview_completed(username):
    file_path = os.path.join(config.TRANSCRIPTS_DIRECTORY, f"{username}_transcript.json"); return os.path.exists(file_path)

# --- Interview Save (Keep as is - already handles transcript formatting) ---
def save_interview_data(username, transcripts_directory, times_directory, file_name_addition_transcript="", file_name_addition_time="", is_final_save=False):
    os.makedirs(transcripts_directory, exist_ok=True); os.makedirs(times_directory, exist_ok=True)
    transcript_filename = f"{username}{file_name_addition_transcript}_transcript.json"; transcript_path = os.path.join(transcripts_directory, transcript_filename)
    formatted_transcript_string = ""
    try:
        with open(transcript_path, "w", encoding='utf-8') as f: json.dump(st.session_state.messages, f, indent=4, ensure_ascii=False)
        print(f"Transcript saved to {transcript_path}")
        if is_final_save:
            lines = []
            for message in st.session_state.messages:
                if message['role'] == 'system': continue
                if message['content'] in config.CLOSING_MESSAGES.keys(): continue
                lines.append(f"{message['role'].capitalize()}: {message['content']}")
            formatted_transcript_string = "\n---\n".join(lines); st.session_state.formatted_transcript = formatted_transcript_string
            print("Formatted transcript stored in session state for survey.")
    except Exception as e: print(f"Error saving transcript to {transcript_path}: {e}"); st.error(f"Error saving transcript: {e}")
    time_filename = f"{username}{file_name_addition_time}_time.csv"; time_path = os.path.join(times_directory, time_filename)
    try:
        end_time = time.time(); start_time = st.session_state.start_time; duration_seconds = round(end_time - start_time) if start_time else 0
        duration_minutes = duration_seconds / 60.0; start_time_utc_str = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(start_time)) if start_time else "N/A"
        time_df = pd.DataFrame({"username": [username], "start_time_unix": [start_time], "start_time_utc": [start_time_utc_str], "end_time_unix": [end_time], "duration_seconds": [duration_seconds], "duration_minutes": [duration_minutes]})
        time_df.to_csv(time_path, index=False, encoding='utf-8'); print(f"Time data saved to {time_path}")
    except Exception as e: print(f"Error saving time data to {time_path}: {e}"); st.error(f"Error saving time data: {e}")

# --- Survey Utility Functions ---
def create_survey_directory(): os.makedirs(config.SURVEY_DIRECTORY, exist_ok=True); print(f"Ensured survey directory exists: {config.SURVEY_DIRECTORY}")

# --- Survey Check (Keep as is - handles testaccount) ---
def check_if_survey_completed(username):
    if username == "testaccount": print("Survey check: testaccount detected, allowing retake."); return False
    file_path = os.path.join(config.SURVEY_DIRECTORY, f"{username}_survey.json"); gsheet_check_path = os.path.join(config.SURVEY_DIRECTORY, f"{username}_survey_submitted_gsheet.flag")
    completed = os.path.exists(file_path) or os.path.exists(gsheet_check_path)
    if completed: print(f"Survey check: User '{username}' already completed.")
    return completed

# --- Survey Save Local (Keep as is) ---
def save_survey_data_local(username, survey_responses):
    file_path = os.path.join(config.SURVEY_DIRECTORY, f"{username}_survey.json")
    data_to_save = { "username": username, "submission_timestamp_unix": time.time(), "submission_time_utc": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()), "responses": survey_responses }
    try:
        with open(file_path, "w", encoding='utf-8') as f: json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        print(f"Local survey backup saved for user {username} to {file_path}"); return True
    except Exception as e: st.error(f"Error saving local survey backup: {e}"); print(f"Error saving local survey backup for {username}: {e}"); return False


# --- *** MODIFIED GSheet Save *** ---
def save_survey_data_to_gsheet(username, survey_responses):
    """Saves the NEW survey responses AND formatted transcript to Google Sheets."""
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_dict = st.secrets["connections"]["gsheets"] # Correct nested access
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        sheet_name = "pilot_survey_results" # <<< YOUR ACTUAL SHEET NAME
        worksheet = gc.open(sheet_name).sheet1
        submission_time_utc = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        formatted_transcript = st.session_state.get("formatted_transcript", "Transcript not found.")

        # ** Define row using NEW keys and matching GSheet column order **
        row_to_append = [
            username,                           # Col 1: Username
            submission_time_utc,                # Col 2: Timestamp
            survey_responses.get("age", ""),            # Col 3: Age (key from widget)
            survey_responses.get("gender", ""),         # Col 4: Gender (key from widget)
            survey_responses.get("major", ""),          # Col 5: Major (key from widget)
            survey_responses.get("year", ""),           # Col 6: Year of Study (key from widget)
            survey_responses.get("gpa", ""),            # Col 7: GPA (key from widget)
            survey_responses.get("ai_frequency", ""),   # Col 8: AI Use Frequency (key from widget)
            survey_responses.get("ai_model", ""),       # Col 9: AI Model Name (key from widget)
            formatted_transcript                # Col 10: Transcript
        ]

        worksheet.append_row(row_to_append, value_input_option='USER_ENTERED')
        print(f"Survey data & transcript for {username} appended to Google Sheet '{sheet_name}'.")

        if username != "testaccount":
             flag_file_path = os.path.join(config.SURVEY_DIRECTORY, f"{username}_survey_submitted_gsheet.flag")
             with open(flag_file_path, 'w') as f: f.write(f"Submitted at {submission_time_utc}")
             print(f"Completion flag file created for {username}.")
        else:
             print(f"Skipping completion flag file for testaccount.")
        return True
    except gspread.exceptions.SpreadsheetNotFound: st.error(f"Error: Spreadsheet '{sheet_name}' not found. Check name/sharing."); print(f"Spreadsheet '{sheet_name}' not found."); return False
    except KeyError as e:
         if "connections" in str(e) or "gsheets" in str(e): st.error("Error accessing secrets. Check [connections.gsheets] in secrets.toml."); print(f"Error accessing secrets: {e}")
         else: st.error(f"An unexpected KeyError occurred: {e}"); print(f"An unexpected KeyError occurred: {e}")
         return False
    except Exception as e: st.error(f"An error occurred saving to Google Sheets: {e}"); print(f"Error saving survey data for {username} to GSheet: {e}"); return False

# --- Main Survey Save (Keep as is) ---
def save_survey_data(username, survey_responses):
    create_survey_directory()
    gsheet_success = save_survey_data_to_gsheet(username, survey_responses)
    if gsheet_success:
        save_survey_data_local(username, survey_responses) # Optional local backup
        return True
    else:
        return False