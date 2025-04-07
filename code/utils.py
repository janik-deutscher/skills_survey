# utils.py
import streamlit as st
import hmac # Only needed if using check_password with hmac
import time
import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import config
# import numpy as np # Not needed directly in utils anymore

# --- Password Check (Keep function signature if config.LOGINS might be True, otherwise remove) ---
# def check_password():
#     """ Example: Returns 'True' if the user has entered a correct password."""
#     # Implement your login logic here if config.LOGINS is True
#     # ... (your previous check_password code or authenticator logic) ...
#     # return False, None # Default if login not implemented/fails
#     pass # Remove if not using logins at all


# --- Interview Check ---
def check_if_interview_completed(username):
    """Checks if the final interview transcript JSON file exists for the user."""
    file_path = os.path.join(config.TRANSCRIPTS_DIRECTORY, f"{username}_transcript.json")
    return os.path.exists(file_path)


# --- Interview Save ---
def save_interview_data(
    username,
    transcripts_directory,
    times_directory,
    file_name_addition_transcript="",
    file_name_addition_time="",
    is_final_save=False
):
    """Write interview data (transcript as JSON, time as CSV) to disk.
       If is_final_save, format transcript and store in session state."""
    os.makedirs(transcripts_directory, exist_ok=True)
    os.makedirs(times_directory, exist_ok=True)

    transcript_filename = f"{username}{file_name_addition_transcript}_transcript.json"
    transcript_path = os.path.join(transcripts_directory, transcript_filename)
    formatted_transcript_string = ""

    try:
        # Save JSON transcript
        with open(transcript_path, "w", encoding='utf-8') as f:
            json.dump(st.session_state.messages, f, indent=4, ensure_ascii=False)
        print(f"Transcript saved to {transcript_path}")

        # If final save, format transcript for GSheet
        if is_final_save and "messages" in st.session_state:
            lines = []
            for message in st.session_state.messages:
                if message['role'] == 'system': continue
                if message['content'] in config.CLOSING_MESSAGES.keys(): continue # Skip raw code
                lines.append(f"{message['role'].capitalize()}: {message['content']}")
            formatted_transcript_string = "\n---\n".join(lines)
            st.session_state.formatted_transcript = formatted_transcript_string # Store in session
            print("Formatted transcript stored in session state.")

    except Exception as e:
        print(f"Error saving transcript to {transcript_path}: {e}")
        st.error(f"Error saving transcript: {e}")

    # Save timing data
    time_filename = f"{username}{file_name_addition_time}_time.csv"
    time_path = os.path.join(times_directory, time_filename)
    try:
        end_time = time.time()
        start_time = st.session_state.get("start_time", None) # Use .get for safety
        duration_seconds = round(end_time - start_time) if start_time else 0
        duration_minutes = duration_seconds / 60.0
        start_time_utc_str = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(start_time)) if start_time else "N/A"

        time_df = pd.DataFrame({
            "username": [username], "start_time_unix": [start_time], "start_time_utc": [start_time_utc_str],
            "end_time_unix": [end_time], "duration_seconds": [duration_seconds], "duration_minutes": [duration_minutes]
        })
        time_df.to_csv(time_path, index=False, encoding='utf-8')
        print(f"Time data saved to {time_path}")
    except Exception as e:
        print(f"Error saving time data to {time_path}: {e}")
        st.error(f"Error saving time data: {e}")


# --- Survey Utility Functions ---
def create_survey_directory():
    """Creates the survey directory defined in config if it doesn't exist."""
    os.makedirs(config.SURVEY_DIRECTORY, exist_ok=True)
    # print(f"Ensured survey directory exists: {config.SURVEY_DIRECTORY}") # Less verbose


def check_if_survey_completed(username):
    """Checks if survey completed, BUT always returns False for 'testaccount'."""
    if username == "testaccount":
        # print("Survey check: testaccount detected, allowing retake.") # Less verbose
        return False # Allow testaccount to always retake

    # Check for flag file (preferred check for non-test users)
    gsheet_check_path = os.path.join(config.SURVEY_DIRECTORY, f"{username}_survey_submitted_gsheet.flag")
    if os.path.exists(gsheet_check_path):
        # print(f"Survey check: User '{username}' completed (flag file found).") # Less verbose
        return True

    # Fallback: check for local JSON file (if flag file somehow failed)
    # json_file_path = os.path.join(config.SURVEY_DIRECTORY, f"{username}_survey.json")
    # if os.path.exists(json_file_path):
    #     print(f"Survey check: User '{username}' completed (JSON file found).") # Less verbose
    #     return True

    return False # Not completed


def save_survey_data_local(username, survey_responses):
    """Saves the survey responses locally as a JSON file (optional backup)."""
    # Skip local save for testaccount to prevent clutter? Optional.
    # if username == "testaccount": return True

    file_path = os.path.join(config.SURVEY_DIRECTORY, f"{username}_survey.json")
    data_to_save = {
        "username": username,
        "submission_timestamp_unix": time.time(),
        "submission_time_utc": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
        "responses": survey_responses
    }
    try:
        with open(file_path, "w", encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        # print(f"Local survey backup saved for user {username} to {file_path}") # Less verbose
        return True
    except Exception as e:
        st.error(f"Error saving local survey backup: {e}")
        print(f"Error saving local survey backup for {username}: {e}")
        return False


def save_survey_data_to_gsheet(username, survey_responses):
    """Saves the survey responses AND formatted transcript to Google Sheets."""
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_dict = st.secrets["connections"]["gsheets"] # Nested access
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)

        # !!! IMPORTANT: CHANGE THIS TO YOUR ACTUAL GOOGLE SHEET NAME !!!
        sheet_name = "pilot_survey_results"
        # !!! IMPORTANT: CHANGE THIS TO YOUR ACTUAL GOOGLE SHEET NAME !!!

        worksheet = gc.open(sheet_name).sheet1
        submission_time_utc = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        # Retrieve formatted transcript from session state
        formatted_transcript = st.session_state.get("formatted_transcript", "ERROR: Transcript not found in session.")

        # Define row - ENSURE THIS ORDER MATCHES YOUR GOOGLE SHEET HEADERS EXACTLY
        row_to_append = [
            username,                           # Col 1: Username
            submission_time_utc,                # Col 2: Timestamp
            survey_responses.get("age", ""),            # Col 3: Age
            survey_responses.get("gender", ""),         # Col 4: Gender
            survey_responses.get("major", ""),          # Col 5: Major
            survey_responses.get("year", ""),           # Col 6: Year of Study
            survey_responses.get("gpa", ""),            # Col 7: GPA
            survey_responses.get("ai_frequency", ""),   # Col 8: AI Use Frequency
            survey_responses.get("ai_model", ""),       # Col 9: AI Model Name
            formatted_transcript                # Col 10: Transcript
        ]

        worksheet.append_row(row_to_append, value_input_option='USER_ENTERED')
        print(f"Survey data & transcript for {username} appended to Google Sheet '{sheet_name}'.")

        # Create flag file only for non-test accounts to prevent retakes
        if username != "testaccount":
             flag_file_path = os.path.join(config.SURVEY_DIRECTORY, f"{username}_survey_submitted_gsheet.flag")
             try:
                 with open(flag_file_path, 'w') as f:
                     f.write(f"Submitted at {submission_time_utc}")
                 print(f"Completion flag file created for {username}.")
             except Exception as flag_e:
                 print(f"Error creating flag file for {username}: {flag_e}") # Log error but don't stop GSheet success
        # else:
             # print(f"Skipping completion flag file for testaccount.") # Less verbose

        return True # GSheet save successful

    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: Spreadsheet '{sheet_name}' not found. Please ensure the name in utils.py is EXACTLY correct and the sheet is shared with the service account email: {creds_dict.get('client_email')}")
        print(f"Spreadsheet '{sheet_name}' not found for service account {creds_dict.get('client_email')}.")
        return False
    except Exception as e:
        st.error(f"An error occurred saving to Google Sheets: {e}. Please check sheet sharing, column headers, and API permissions.")
        print(f"Error saving survey data for {username} to GSheet: {e}")
        return False


def save_survey_data(username, survey_responses):
    """Main function to save survey data. Tries GSheet first."""
    create_survey_directory()
    gsheet_success = save_survey_data_to_gsheet(username, survey_responses)

    if gsheet_success:
        # Save local backup only AFTER successful GSheet save (optional)
        save_survey_data_local(username, survey_responses)
        return True
    else:
        # Primary save target (GSheet) failed
        return False