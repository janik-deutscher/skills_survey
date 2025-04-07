# app.py
import streamlit as st
import time
import pandas as pd
from utils import (
    # check_password, # Only needed if LOGINS=True
    check_if_interview_completed,
    save_interview_data,
    check_if_survey_completed,
    save_survey_data # Main survey save function
)
import os
import config
import json
import numpy as np
import uuid

# --- Constants ---
WELCOME_STAGE = "welcome" # New stage
INTERVIEW_STAGE = "interview"
SURVEY_STAGE = "survey"
COMPLETED_STAGE = "completed"

# --- API Setup ---
# (Keep your existing API setup block)
if "gpt" in config.MODEL.lower():
    api = "openai"; from openai import OpenAI
    try: client = OpenAI(api_key=st.secrets["API_KEY_OPENAI"])
    except KeyError: st.error("Error: OpenAI API key ('API_KEY_OPENAI') not found."); st.stop()
    except Exception as e: st.error(f"Error initializing OpenAI client: {e}"); st.stop()
elif "claude" in config.MODEL.lower():
    api = "anthropic"; import anthropic
    try: client = anthropic.Anthropic(api_key=st.secrets["API_KEY_ANTHROPIC"])
    except KeyError: st.error("Error: Anthropic API key ('API_KEY_ANTHROPIC') not found."); st.stop()
    except Exception as e: st.error(f"Error initializing Anthropic client: {e}"); st.stop()
else: st.error("Model name must contain 'gpt' or 'claude'."); st.stop()

# --- Page Config ---
st.set_page_config(page_title="Skills & AI Interview", page_icon=config.AVATAR_INTERVIEWER)


# --- User Identification ---
query_params = st.query_params.to_dict()
test_user_requested = query_params.get("username", [""])[0] == "testaccount"

# Initialize username and welcome flag if they don't exist
if "username" not in st.session_state:
    st.session_state.username = None # Ensure it exists even if None initially
if "welcome_shown" not in st.session_state:
     st.session_state.welcome_shown = False

# Assign or generate username only if it hasn't been set yet in this session
if st.session_state.username is None:
    if test_user_requested:
        st.session_state.username = "testaccount"; st.session_state.is_test_account = True
        print("INFO: Using 'testaccount' via query param.")
        st.rerun() # Rerun once after setting username
    elif config.LOGINS:
         # Add Login logic here if needed, setting st.session_state.username
         st.warning("Login configured but using UUID fallback."); st.session_state.username = f"user_{uuid.uuid4()}"; st.session_state.is_test_account = False
         st.rerun() # Rerun once after setting username
    else: # No logins, no test param
        st.session_state.username = f"user_{uuid.uuid4()}"; st.session_state.is_test_account = False
        print(f"INFO: Generated new user UUID: {st.session_state.username}")
        st.rerun() # Rerun once after setting username

# Retrieve username for use (should exist now)
username = st.session_state.username
is_test_account = st.session_state.get("is_test_account", False)

# --- Directory Creation (Only if username is set) ---
if username:
    try:
        os.makedirs(config.TRANSCRIPTS_DIRECTORY, exist_ok=True); os.makedirs(config.TIMES_DIRECTORY, exist_ok=True)
        os.makedirs(config.BACKUPS_DIRECTORY, exist_ok=True); os.makedirs(config.SURVEY_DIRECTORY, exist_ok=True)
    except OSError as e: st.error(f"Failed to create data directories: {e}."); st.stop()


# --- Initialize Other Session State Variables ---
def initialize_session_state():
    if "username" in st.session_state and st.session_state.username:
        if "current_stage" not in st.session_state: st.session_state.current_stage = None
        # Initialize other states only if not already set
        if "messages" not in st.session_state: st.session_state.messages = []
        if "start_time" not in st.session_state: st.session_state.start_time = None
        if "start_time_file_names" not in st.session_state: st.session_state.start_time_file_names = None
        if "interview_active" not in st.session_state: st.session_state.interview_active = False
        if "interview_completed_flag" not in st.session_state: st.session_state.interview_completed_flag = False
        if "survey_completed_flag" not in st.session_state: st.session_state.survey_completed_flag = False
initialize_session_state()


# --- Determine Current Stage Based on Completion Checks ---
# Determine stage only if username is set and welcome has been shown (or completion overrides welcome)
current_stage = None
if username:
    survey_done = check_if_survey_completed(username)
    st.session_state.survey_completed_flag = survey_done

    if survey_done:
        current_stage = COMPLETED_STAGE
        st.session_state.welcome_shown = True # If completed, welcome is implicitly done
    elif not st.session_state.welcome_shown: # Check if welcome needs to be shown
         current_stage = WELCOME_STAGE
    else: # Welcome shown, survey not done -> check interview
        interview_done = check_if_interview_completed(username)
        st.session_state.interview_completed_flag = interview_done
        if interview_done:
            current_stage = SURVEY_STAGE
        else:
            current_stage = INTERVIEW_STAGE
# Store determined stage
if current_stage:
    st.session_state.current_stage = current_stage


# --- === Main Application Logic === ---

# --- Section 0: Welcome Stage ---
if st.session_state.get("current_stage") == WELCOME_STAGE:
    st.title("Welcome!")
    st.markdown("""
    Hi there, and thanks for participating in this research project!

    We're exploring university students' and recent graduates' perspectives on valuable job skills,
    the influence of Artificial Intelligence (AI), and how these thoughts relate to educational choices.

    This involves two short parts:
    1.  A brief **interview** with an AI assistant (around 10-15 minutes).
    2.  A quick **survey** with some follow-up questions.

    Your anonymous responses are valuable and will contribute to PhD research.
    Please answer thoughtfully and honestly.

    Click the button below when you're ready to begin the interview.
    """)

    if st.button("Start Interview", key="start_interview_btn"):
        st.session_state.welcome_shown = True
        st.session_state.current_stage = INTERVIEW_STAGE # Explicitly set next stage
        st.rerun() # Rerun to move to the interview stage

# --- Section 1: Interview Stage ---
elif st.session_state.get("current_stage") == INTERVIEW_STAGE:
    st.title("Part 1: Interview")
    # --- Start of Interview Logic ---
    st.session_state.interview_active = True
    if st.session_state.start_time is None: # Init time only when entering interview stage
        st.session_state.start_time = time.time()
        st.session_state.start_time_file_names = time.strftime("%Y%m%d_%H%M%S", time.localtime(st.session_state.start_time))
    st.info("Please answer the interviewer's questions.")
    if st.button("Quit Interview Early", key="quit_interview"): # Removed help text for cleaner look
        st.session_state.interview_active = False; st.session_state.interview_completed_flag = True
        quit_message = "You have chosen to end the interview early. Proceeding to the final questions."
        if st.session_state.messages: st.session_state.messages.append({"role": "assistant", "content": quit_message})
        else: st.session_state.messages = [{"role": "system", "content": config.SYSTEM_PROMPT},{"role": "assistant", "content": quit_message}]
        save_interview_data(username=username, transcripts_directory=config.TRANSCRIPTS_DIRECTORY, times_directory=config.TIMES_DIRECTORY, is_final_save=True)
        st.warning(quit_message); st.session_state.current_stage = SURVEY_STAGE; time.sleep(1); st.rerun()

    # Display Chat History
    for message in st.session_state.messages:
        if api == "openai" and message["role"] == "system": continue
        if message["content"] in config.CLOSING_MESSAGES.keys(): continue
        avatar = config.AVATAR_INTERVIEWER if message["role"] == "assistant" else config.AVATAR_RESPONDENT
        with st.chat_message(message["role"], avatar=avatar): st.markdown(message["content"])

    # Initial Interviewer Message
    if not st.session_state.messages:
        try:
            if api == "openai": st.session_state.messages.append({"role": "system", "content": config.SYSTEM_PROMPT})
            with st.chat_message("assistant", avatar=config.AVATAR_INTERVIEWER):
                # ... (rest of initial message logic - no changes needed) ...
                message_placeholder = st.empty(); message_interviewer = ""
                api_kwargs = { "model": config.MODEL, "messages": st.session_state.messages, "max_tokens": config.MAX_OUTPUT_TOKENS, "stream": True }
                if api == "anthropic":
                    api_kwargs["system"] = config.SYSTEM_PROMPT
                    if not any(m['role'] == 'user' for m in api_kwargs["messages"]): api_kwargs["messages"] = [{"role": "user", "content": "Please begin the interview."}]
                if config.TEMPERATURE is not None: api_kwargs["temperature"] = config.TEMPERATURE
                if api == "openai": stream = client.chat.completions.create(**api_kwargs); message_interviewer = st.write_stream(stream)
                elif api == "anthropic":
                     with client.messages.stream(**api_kwargs) as stream:
                         for text_delta in stream.text_stream:
                             if text_delta is not None: message_interviewer += text_delta; message_placeholder.markdown(message_interviewer + "▌")
                     message_placeholder.markdown(message_interviewer)
            st.session_state.messages.append({"role": "assistant", "content": message_interviewer})
            if st.session_state.start_time_file_names:
                 backup_suffix = f"_backup_started_{st.session_state.start_time_file_names}"
                 save_interview_data(username=username, transcripts_directory=config.BACKUPS_DIRECTORY, times_directory=config.BACKUPS_DIRECTORY, file_name_addition_transcript=backup_suffix, file_name_addition_time=backup_suffix, is_final_save=False)
            time.sleep(0.1); st.rerun()
        except Exception as e: st.error(f"Failed to get initial message from API: {e}"); st.stop()

    # Main Chat Interaction
    if prompt := st.chat_input("Your response..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar=config.AVATAR_RESPONDENT): st.markdown(prompt)
        try:
            with st.chat_message("assistant", avatar=config.AVATAR_INTERVIEWER):
                # ... (rest of chat interaction logic - no changes needed) ...
                 message_placeholder = st.empty(); message_interviewer = ""; full_response_content = ""
                 api_kwargs = { "model": config.MODEL, "messages": st.session_state.messages, "max_tokens": config.MAX_OUTPUT_TOKENS, "stream": True }
                 if api == "anthropic": api_kwargs["system"] = config.SYSTEM_PROMPT
                 if config.TEMPERATURE is not None: api_kwargs["temperature"] = config.TEMPERATURE
                 stream_closed = False; detected_code = None
                 # Streaming and code detection logic
                 if api == "openai":
                    stream = client.chat.completions.create(**api_kwargs)
                    for chunk in stream: # ... (code detection logic) ...
                         text_delta = chunk.choices[0].delta.content
                         if text_delta:
                             full_response_content += text_delta
                             for code in config.CLOSING_MESSAGES.keys():
                                 if code == full_response_content.strip(): detected_code = code; message_interviewer = full_response_content.replace(code, "").strip(); stream.close(); stream_closed = True; break
                             if stream_closed: break
                             message_interviewer = full_response_content; message_placeholder.markdown(message_interviewer + "▌")
                    if not stream_closed: message_placeholder.markdown(message_interviewer)
                 elif api == "anthropic":
                     with client.messages.stream(**api_kwargs) as stream:
                        for text_delta in stream.text_stream: # ... (code detection logic) ...
                             if text_delta is not None:
                                 full_response_content += text_delta
                                 for code in config.CLOSING_MESSAGES.keys():
                                     if code == full_response_content.strip(): detected_code = code; message_interviewer = full_response_content.replace(code,"").strip(); stream_closed = True; break
                                 if stream_closed: break
                                 message_interviewer = full_response_content; message_placeholder.markdown(message_interviewer + "▌")
                     if not stream_closed: message_placeholder.markdown(message_interviewer)

                 st.session_state.messages.append({"role": "assistant", "content": full_response_content.strip()})
                 # Process closing code
                 if detected_code:
                    st.session_state.interview_active = False; st.session_state.interview_completed_flag = True
                    closing_message_display = config.CLOSING_MESSAGES[detected_code]
                    save_interview_data(username=username, transcripts_directory=config.TRANSCRIPTS_DIRECTORY, times_directory=config.TIMES_DIRECTORY, is_final_save=True)
                    st.success(closing_message_display); st.session_state.current_stage = SURVEY_STAGE; time.sleep(2); st.rerun()
                 else: # Save backup
                     try:
                         if st.session_state.start_time_file_names:
                              backup_suffix = f"_backup_inprogress_{st.session_state.start_time_file_names}"
                              save_interview_data(username=username, transcripts_directory=config.BACKUPS_DIRECTORY, times_directory=config.BACKUPS_DIRECTORY, file_name_addition_transcript=backup_suffix, file_name_addition_time=backup_suffix, is_final_save=False)
                     except Exception as backup_e: print(f"Warning: Backup failed - {backup_e}")
        except Exception as e: st.error(f"An error occurred during the interview chat: {e}")

# --- Section 2: Survey Stage ---
elif st.session_state.get("current_stage") == SURVEY_STAGE:
    st.title("Part 2: Survey")
    st.info(f"Thank you {username}, please answer a few final questions.")
    # --- Start of Survey Logic ---
    # (Keep the entire Survey Definition and Form block - no changes needed)
    age_options = ["Select...", "Under 18"] + [str(i) for i in range(18, 36)] + ["Older than 35"]
    gender_options = ["Select...", "Male", "Female", "Non-binary", "Prefer not to say"]
    major_options = ["Select...", "Computer Science", "Engineering (Other)", "Business", "Humanities", "Social Sciences", "Natural Sciences", "Arts", "Health Sciences", "Other", "Not Applicable"]
    year_options = ["Select...", "1st Year Undergraduate", "2nd Year Undergraduate", "3rd Year Undergraduate", "4th+ Year Undergraduate", "Graduate Student", "Postgraduate/Doctoral", "Not a Student"]
    gpa_values = np.round(np.arange(5.0, 10.01, 0.1), 1); gpa_options = ["Select...", "Below 5.0"] + [f"{gpa:.1f}" for gpa in gpa_values] + ["Prefer not to say / Not applicable"]
    ai_freq_options = ["Select...", "Frequently (Daily/Weekly)", "Occasionally (Monthly)", "Rarely (Few times a year)", "Never", "Unsure"]

    with st.form("survey_form"):
        st.subheader("Demographic Information"); age = st.selectbox("Age?", age_options, key="age"); gender = st.selectbox("Gender?", gender_options, key="gender")
        major = st.selectbox("Major/Field?", major_options, key="major"); year_of_study = st.selectbox("Year?", year_options, key="year")
        gpa = st.selectbox("GPA?", gpa_options, key="gpa")
        st.subheader("AI Usage"); ai_frequency = st.selectbox("AI Use Frequency?", ai_freq_options, key="ai_frequency")
        ai_model = st.text_input("AI Model(s) Used?", key="ai_model")
        submitted = st.form_submit_button("Submit Survey Responses")

    if submitted:
        if (age == "Select..." or gender == "Select..." or major == "Select..." or year_of_study == "Select..." or gpa == "Select..." or ai_frequency == "Select..."):
            st.warning("Please answer all dropdown questions.")
        else:
            survey_responses = {"age": age, "gender": gender, "major": major, "year": year_of_study, "gpa": gpa, "ai_frequency": ai_frequency, "ai_model": ai_model}
            save_successful = save_survey_data(username, survey_responses)
            if save_successful:
                st.session_state.survey_completed_flag = True; st.session_state.current_stage = COMPLETED_STAGE
                st.success("Survey submitted! Thank you."); st.balloons(); time.sleep(3); st.rerun()
            # Else: Error handled in save_survey_data

# --- Section 3: Completed Stage ---
elif st.session_state.get("current_stage") == COMPLETED_STAGE:
    st.title("Thank You!")
    st.success("You have completed the interview and the survey. Your contribution is greatly appreciated!")
    st.markdown("You may now close this window.")

# --- Fallback ---
else:
    # This might show briefly during initial reruns if state isn't set fast enough
    st.spinner("Loading application state...")
    # If it persists, there might be an issue in stage determination logic
    print(f"Info: Reached fallback state. Username: {username}, Stage: {st.session_state.get('current_stage')}")
    time.sleep(0.5) # Give a bit more time
    st.rerun() # Try one more rerun