# utils.py
import streamlit as st
# import hmac # Only needed if using check_password with hmac
import time
import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import config
# import numpy as np # Not needed directly in utils anymore

# --- Password Check (Keep signature if config.LOGINS might be True, otherwise remove) ---
# def check_password():
#     """ Example: Returns 'True' if the user has entered a correct password."""
#     # Implement your login logic here if config.LOGINS is True
#     pass


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

    try:
        # Ensure messages list exists before trying to dump/format
        if "messages" in st.session_state and st.session_state.messages:
            # Save JSON transcript
            with open(transcript_path, "w", encoding='utf-8') as f:
                json.dump(st.session_state.messages, f, indent=4, ensure_ascii=False)
            print(f"Transcript saved to {transcript_path}")

            # If final save, format transcript for GSheet
            if is_final_save:
                lines = []
                for message in st.session_state.messages:
                    if message['role'] == 'system': continue
                    if message['content'] in config.CLOSING_MESSAGES.keys(): continue # Skip raw code
                    lines.append(f"{message['role'].capitalize()}: {message['content']}")
                formatted_transcript_string = "\n---\n".join(lines)
                st.session_state.formatted_transcript = formatted_transcript_string # Store in session
                print("Formatted transcript stored in session state.")
        else:
            print(f"Warning: No messages found in session state for user {username}. Transcript not saved.")
            if is_final_save:
                st.session_state.formatted_transcript = "ERROR: No messages found in session."

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
        # print(f"Time data saved to {time_path}") # Less verbose
    except Exception as e:
        print(f"Error saving time data to {time_path}: {e}")
        st.error(f"Error saving time data: {e}")


# --- Survey Utility Functions ---
def create_survey_directory():
    """Creates the survey directory defined in config if it doesn't exist."""
    os.makedirs(config.SURVEY_DIRECTORY, exist_ok=True)


def check_if_survey_completed(username):
    """Checks if survey completed (via flag file), BUT always returns False for 'testaccount'."""
    if username == "testaccount":
        return False # Allow testaccount to always retake

    # Check for flag file (preferred check for non-test users)
    gsheet_check_path = os.path.join(config.SURVEY_DIRECTORY, f"{username}_survey_submitted_gsheet.flag")
    if os.path.exists(gsheet_check_path):
        return True

    # Optional Fallback: check for local JSON file (can be removed if flag file is reliable)
    # json_file_path = os.path.join(config.SURVEY_DIRECTORY, f"{username}_survey.json")
    # if os.path.exists(json_file_path): return True

    return False # Not completed


def save_survey_data_local(username, survey_responses):
    """Saves the survey responses locally as a JSON file (optional backup)."""
    # Optional: skip local save for testaccount
    # if username == "testaccount": return True

    file_path = os.path.join(config.SURVEY_DIRECTORY, f"{username}_survey.json")
    # Retrieve consent status for local save too? Optional.
    consent_given = st.session_state.get("consent_given", False)
    data_to_save = {
        "username": username,
        "submission_timestamp_unix": time.time(),
        "submission_time_utc": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
        "consent_given": consent_given, # Added consent here too
        "responses": survey_responses
    }
    try:
        with open(file_path, "w", encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error saving local survey backup: {e}")
        print(f"Error saving local survey backup for {username}: {e}")
        return False


def save_survey_data_to_gsheet(username, survey_responses):
    """Saves the survey responses, consent status, AND transcript to Google Sheets."""
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_dict = st.secrets["connections"]["gsheets"] # Nested access
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)

        # !!! IMPORTANT: CHANGE THIS TO YOUR ACTUAL GOOGLE SHEET NAME !!!
        sheet_name = "pilot_survey_results" # e.g., "pilot_survey_results"
        # !!! IMPORTANT: CHANGE THIS TO YOUR ACTUAL GOOGLE SHEET NAME !!!

        worksheet = gc.open(sheet_name).sheet1
        submission_time_utc = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        # Retrieve Consent status and Transcript from session state
        consent_given = st.session_state.get("consent_given", "ERROR: Consent status missing") # Get consent status
        formatted_transcript = st.session_state.get("formatted_transcript", "ERROR: Transcript not found.")

        # Define row - ENSURE THIS ORDER MATCHES YOUR GOOGLE SHEET HEADERS EXACTLY
        row_to_append = [
            username,                           # Col A: Username
            submission_time_utc,                # Col B: Timestamp
            str(consent_given),                 # Col C: Consent Given (as "True" or "False" string)
            survey_responses.get("age", ""),            # Col D: Age
            survey_responses.get("gender", ""),         # Col E: Gender
            survey_responses.get("major", ""),          # Col F: Major
            survey_responses.get("year", ""),           # Col G: Year of Study
            survey_responses.get("gpa", ""),            # Col H: GPA
            survey_responses.get("ai_frequency", ""),   # Col I: AI Use Frequency
            survey_responses.get("ai_model", ""),       # Col J: AI Model Name
            formatted_transcript                # Col K: Transcript
        ]

        worksheet.append_row(row_to_append, value_input_option='USER_ENTERED')
        print(f"Survey data (consent={consent_given}) & transcript for {username} appended to GSheet '{sheet_name}'.")

        # Create flag file only for non-test accounts
        if username != "testaccount":
             flag_file_path = os.path.join(config.SURVEY_DIRECTORY, f"{username}_survey_submitted_gsheet.flag")
             try:
                 with open(flag_file_path, 'w') as f: f.write(f"Submitted at {submission_time_utc}")
                 print(f"Completion flag file created for {username}.")
             except Exception as flag_e: print(f"Error creating flag file for {username}: {flag_e}")

        return True # GSheet save successful

    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: Spreadsheet '{sheet_name}' not found. Ensure name in utils.py is correct & sheet shared with: {creds_dict.get('client_email')}")
        print(f"Spreadsheet '{sheet_name}' not found for service account {creds_dict.get('client_email')}.")
        return False
    except Exception as e:
        st.error(f"An error occurred saving to Google Sheets: {e}. Check sharing, headers, API permissions.")
        print(f"Error saving survey data for {username} to GSheet: {e}")
        return False


def save_survey_data(username, survey_responses):
    """Main function to save survey data. Tries GSheet first, optional local backup."""
    create_survey_directory()
    gsheet_success = save_survey_data_to_gsheet(username, survey_responses)

    if gsheet_success:
        # Save local backup only AFTER successful GSheet save (optional)
        save_survey_data_local(username, survey_responses)
        return True
    else:
        # Primary save target (GSheet) failed
        return False