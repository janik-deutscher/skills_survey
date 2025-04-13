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
# (Make sure this matches your model and secrets setup)
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

# Initialize states if they don't exist
if "username" not in st.session_state: st.session_state.username = None
if "welcome_shown" not in st.session_state: st.session_state.welcome_shown = False
if "consent_given" not in st.session_state: st.session_state.consent_given = False

# Assign or generate username only if it hasn't been set yet
if st.session_state.username is None:
    if test_user_requested:
        st.session_state.username = "testaccount"; st.session_state.is_test_account = True
        print("INFO: Using 'testaccount' via query param."); st.rerun()
    elif config.LOGINS:
         # Placeholder: Implement actual login if needed
         st.warning("Login configured but using UUID fallback."); st.session_state.username = f"user_{uuid.uuid4()}"; st.session_state.is_test_account = False
         st.rerun()
    else: # No logins, no test param
        st.session_state.username = f"user_{uuid.uuid4()}"; st.session_state.is_test_account = False
        print(f"INFO: Generated new user UUID: {st.session_state.username}"); st.rerun()

# Retrieve username for use
username = st.session_state.username
is_test_account = st.session_state.get("is_test_account", False)

# --- Directory Creation ---
if username:
    try:
        os.makedirs(config.TRANSCRIPTS_DIRECTORY, exist_ok=True); os.makedirs(config.TIMES_DIRECTORY, exist_ok=True)
        os.makedirs(config.BACKUPS_DIRECTORY, exist_ok=True); os.makedirs(config.SURVEY_DIRECTORY, exist_ok=True)
    except OSError as e: st.error(f"Failed to create data directories: {e}."); st.stop()


# --- Initialize Other Session State Variables ---
def initialize_session_state():
    if "username" in st.session_state and st.session_state.username:
        if "current_stage" not in st.session_state: st.session_state.current_stage = None
        if "messages" not in st.session_state: st.session_state.messages = []
        if "start_time" not in st.session_state: st.session_state.start_time = None
        if "start_time_file_names" not in st.session_state: st.session_state.start_time_file_names = None
        if "interview_active" not in st.session_state: st.session_state.interview_active = False
        if "interview_completed_flag" not in st.session_state: st.session_state.interview_completed_flag = False
        if "survey_completed_flag" not in st.session_state: st.session_state.survey_completed_flag = False
initialize_session_state()


# --- Determine Current Stage Based on Completion Checks ---
current_stage = None
if username:
    survey_done = check_if_survey_completed(username)
    st.session_state.survey_completed_flag = survey_done

    if survey_done:
        current_stage = COMPLETED_STAGE
        st.session_state.welcome_shown = True # Mark welcome done if survey done
    elif not st.session_state.welcome_shown:
         current_stage = WELCOME_STAGE
    else: # Welcome shown, survey not done
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
    st.title("Welcome & Consent")

    st.markdown("""
    Hi there, and thanks for participating in this research project!

    I'm Janik's AI assistant helping him in his PhD project exploring university students' perspectives on valuable job skills,
    the influence of Artificial Intelligence (AI), and how these thoughts relate to educational choices.

    This involves two short parts:
    1.  A brief **interview** with an AI assistant (around 10-15 minutes).
    2.  A quick **survey** with some basic questions about you and your study background.
    """)

    st.markdown("---") # Separator

    # --- Data Protection Information ---
    # !!! IMPORTANT: REPLACE THIS WITH YOUR ACTUAL GDPR/ETHICS TEXT !!!
    st.subheader("Data Protection & Consent")
    st.markdown("""
    **Please read the following information carefully:**

    *   **Purpose:** The data collected (interview transcript and survey answers) will be used solely for PhD research purposes related to understanding skill perceptions and AI influence.
    *   **Anonymity:** Your responses will be anonymized. The unique ID generated for this session is not linked to your personal identity. Any potentially identifying information mentioned during the interview will be removed or pseudonymized during analysis. Your name or email address is not collected.
    *   **Data Storage:** Anonymized data will be stored securely.
    *   **Withdrawal:** You can stop the interview at any time using the "Quit" button. You can choose not to answer any question in the survey. Once submitted, removing your specific anonymized data may be difficult, but you can contact [Your Name/Email Address] with your session UserID (if known) if you have concerns.
    *   **Contact:** If you have questions about this study or your rights, please contact Janik Deutscher (janik.deutscher@upf.edu) or the UPF's Ethics Committee.

    """)

    # --- Consent Checkbox ---
    consent = st.checkbox("I confirm that I have read and understood the information above, I am 18 years or older, and I voluntarily consent to participate in this study.", key="consent_checkbox", value=st.session_state.consent_given) # Reflect current state

    # Store consent checkbox state immediately
    st.session_state.consent_given = consent

    # --- Start Button (Disabled until consent is given) ---
    if st.button("Start Interview", key="start_interview_btn", disabled=not st.session_state.consent_given):
        if st.session_state.consent_given: # Double check state just before proceeding
            st.session_state.welcome_shown = True
            st.session_state.current_stage = INTERVIEW_STAGE # Explicitly set next stage
            st.rerun()
    elif not st.session_state.consent_given:
        # This message will show if the button is visible but disabled (it shouldn't be due to 'disabled' arg, but safe fallback)
        # A better approach is implied feedback: the button is simply unclickable until box is checked.
        # st.warning("Please check the consent box above to proceed.")
        pass


# --- Section 1: Interview Stage ---
elif st.session_state.get("current_stage") == INTERVIEW_STAGE:
    st.title("Part 1: Interview")
    st.session_state.interview_active = True
    if st.session_state.start_time is None:
        st.session_state.start_time = time.time(); st.session_state.start_time_file_names = time.strftime("%Y%m%d_%H%M%S", time.localtime(st.session_state.start_time))
    st.info("Please answer the interviewer's questions.")
    if st.button("Quit Interview Early", key="quit_interview"):
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
                 message_placeholder = st.empty(); message_interviewer = ""; full_response_content = ""
                 api_kwargs = { "model": config.MODEL, "messages": st.session_state.messages, "max_tokens": config.MAX_OUTPUT_TOKENS, "stream": True }
                 if api == "anthropic": api_kwargs["system"] = config.SYSTEM_PROMPT
                 if config.TEMPERATURE is not None: api_kwargs["temperature"] = config.TEMPERATURE
                 stream_closed = False; detected_code = None
                 # Streaming and code detection logic
                 if api == "openai":
                    stream = client.chat.completions.create(**api_kwargs)
                    for chunk in stream:
                         text_delta = chunk.choices[0].delta.content
                         if text_delta:
                             full_response_content += text_delta
                             for code in config.CLOSING_MESSAGES.keys():
                                 if code == full_response_content.strip(): detected_code = code; message_interviewer = full_response_content.replace(code, "").strip(); # ... (placeholder/close handling) ...; stream.close(); stream_closed = True; break
                             if stream_closed: break
                             message_interviewer = full_response_content; message_placeholder.markdown(message_interviewer + "▌")
                    if not stream_closed: message_placeholder.markdown(message_interviewer)
                 elif api == "anthropic":
                     with client.messages.stream(**api_kwargs) as stream:
                        for text_delta in stream.text_stream:
                             if text_delta is not None:
                                 full_response_content += text_delta
                                 for code in config.CLOSING_MESSAGES.keys():
                                     if code == full_response_content.strip(): detected_code = code; message_interviewer = full_response_content.replace(code,"").strip(); # ... (placeholder handling) ...; stream_closed = True; break
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
    # Survey options definitions
    age_options = ["Select...", "Under 18"] + [str(i) for i in range(18, 36)] + ["Older than 35"]; gender_options = ["Select...", "Male", "Female", "Non-binary", "Prefer not to say"]; major_options = ["Select...", "Computer Science", "Engineering (Other)", "Business", "Humanities", "Social Sciences", "Natural Sciences", "Arts", "Health Sciences", "Other", "Not Applicable"]; year_options = ["Select...", "1st Year Undergraduate", "2nd Year Undergraduate", "3rd Year Undergraduate", "4th+ Year Undergraduate", "Graduate Student", "Postgraduate/Doctoral", "Not a Student"]; gpa_values = np.round(np.arange(5.0, 10.01, 0.1), 1); gpa_options = ["Select...", "Below 5.0"] + [f"{gpa:.1f}" for gpa in gpa_values] + ["Prefer not to say / Not applicable"]; ai_freq_options = ["Select...", "Frequently (Daily/Weekly)", "Occasionally (Monthly)", "Rarely (Few times a year)", "Never", "Unsure"]

    # Survey form
    with st.form("survey_form"):
        st.subheader("Demographic Information"); age = st.selectbox("Age?", age_options, key="age"); gender = st.selectbox("Gender?", gender_options, key="gender"); major = st.selectbox("Major/Field?", major_options, key="major"); year_of_study = st.selectbox("Year?", year_options, key="year"); gpa = st.selectbox("GPA?", gpa_options, key="gpa")
        st.subheader("AI Usage"); ai_frequency = st.selectbox("AI Use Frequency?", ai_freq_options, key="ai_frequency"); ai_model = st.text_input("AI Model(s) Used?", key="ai_model")
        submitted = st.form_submit_button("Submit Survey Responses")

    # Form submission handling
    if submitted:
        if (age == "Select..." or gender == "Select..." or major == "Select..." or year_of_study == "Select..." or gpa == "Select..." or ai_frequency == "Select..."):
            st.warning("Please answer all dropdown questions.")
        else:
            survey_responses = {"age": age, "gender": gender, "major": major, "year": year_of_study, "gpa": gpa, "ai_frequency": ai_frequency, "ai_model": ai_model}
            # Consent status was already stored in session_state in the Welcome stage
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
    # Handles state where username might be set but stage isn't determined yet (e.g., during initial reruns)
    st.spinner("Loading application state...")
    print(f"Info: Fallback state. User: {username}, Stage: {st.session_state.get('current_stage')}, Welcome: {st.session_state.get('welcome_shown')}")
    time.sleep(0.5) # Give a bit more time for state to sync
    st.rerun()