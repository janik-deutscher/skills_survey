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
import numpy as np # Needed for GPA range generation
import uuid # Import UUID library

# --- Constants ---
INTERVIEW_STAGE = "interview"
SURVEY_STAGE = "survey"
COMPLETED_STAGE = "completed"

# --- API Setup ---
# (Make sure this matches your model and secrets setup)
if "gpt" in config.MODEL.lower():
    api = "openai"
    from openai import OpenAI
    try: client = OpenAI(api_key=st.secrets["API_KEY_OPENAI"])
    except KeyError: st.error("Error: OpenAI API key ('API_KEY_OPENAI') not found in Streamlit secrets."); st.stop()
    except Exception as e: st.error(f"Error initializing OpenAI client: {e}"); st.stop()
elif "claude" in config.MODEL.lower():
    api = "anthropic"
    import anthropic
    try: client = anthropic.Anthropic(api_key=st.secrets["API_KEY_ANTHROPIC"])
    except KeyError: st.error("Error: Anthropic API key ('API_KEY_ANTHROPIC') not found in Streamlit secrets."); st.stop()
    except Exception as e: st.error(f"Error initializing Anthropic client: {e}"); st.stop()
else:
    st.error("Model name in config.py must contain 'gpt' or 'claude'."); st.stop()

# --- Page Config ---
st.set_page_config(page_title="Skills & AI Interview", page_icon=config.AVATAR_INTERVIEWER)


# --- User Identification (UUID or testaccount query param) ---
query_params = st.query_params.to_dict()
test_user_requested = query_params.get("username", [""])[0] == "testaccount"

if "username" not in st.session_state:
    if test_user_requested:
        st.session_state.username = "testaccount"
        print("INFO: Using 'testaccount' based on query parameter.")
        st.session_state.is_test_account = True
    elif config.LOGINS:
         # Placeholder: Implement actual login using check_password if needed
         st.warning("Login configured but using UUID fallback.")
         st.session_state.username = f"user_{uuid.uuid4()}"
         st.session_state.is_test_account = False
         st.rerun() # Rerun after generating UUID
    else: # config.LOGINS is False and not testaccount query param
        st.session_state.username = f"user_{uuid.uuid4()}"
        st.session_state.is_test_account = False
        print(f"INFO: Generated new user UUID: {st.session_state.username}")
        st.rerun() # Rerun *once* after setting the username

# Ensure username is retrieved for use
username = st.session_state.username
is_test_account = st.session_state.get("is_test_account", False)

# Optional: Display user ID in sidebar for debugging
# st.sidebar.write(f"UserID: {username}")


# --- Directory Creation ---
if "username" in st.session_state and st.session_state.username : # Ensure username exists before creating dirs
    try:
        os.makedirs(config.TRANSCRIPTS_DIRECTORY, exist_ok=True)
        os.makedirs(config.TIMES_DIRECTORY, exist_ok=True)
        os.makedirs(config.BACKUPS_DIRECTORY, exist_ok=True)
        os.makedirs(config.SURVEY_DIRECTORY, exist_ok=True)
    except OSError as e:
        st.error(f"Failed to create data directories: {e}.")
        st.stop()


# --- Initialize Session State Variables ---
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
if "username" in st.session_state and st.session_state.username:
    current_username = st.session_state.username
    survey_done = check_if_survey_completed(current_username)
    st.session_state.survey_completed_flag = survey_done

    if survey_done:
        st.session_state.current_stage = COMPLETED_STAGE
    else:
        # Check interview completion (utils function handles this check)
        # No special testaccount logic needed here unless interview retakes also desired
        interview_done = check_if_interview_completed(current_username)
        st.session_state.interview_completed_flag = interview_done

        if interview_done:
            st.session_state.current_stage = SURVEY_STAGE
        else:
            st.session_state.current_stage = INTERVIEW_STAGE
else:
    st.session_state.current_stage = None # Waiting for username generation/rerun


# --- === Main Application Logic === ---

if st.session_state.get("current_stage") is None:
    st.spinner("Initializing session...")
    time.sleep(0.2) # Short pause allows state to settle after rerun
    st.rerun() # Trigger another check cycle


# --- Section 1: Interview Stage ---
elif st.session_state.current_stage == INTERVIEW_STAGE:
    st.title("Part 1: Interview")
    st.session_state.interview_active = True

    if st.session_state.start_time is None:
        st.session_state.start_time = time.time()
        st.session_state.start_time_file_names = time.strftime("%Y%m%d_%H%M%S", time.localtime(st.session_state.start_time))

    st.info("Please answer the interviewer's questions.")

    # Quit Button
    if st.button("Quit Interview Early", key="quit_interview", help="End the interview now and proceed."):
        st.session_state.interview_active = False
        st.session_state.interview_completed_flag = True
        quit_message = "You have chosen to end the interview early. Proceeding to the final questions."
        if st.session_state.messages:
             st.session_state.messages.append({"role": "assistant", "content": quit_message})
        else: # Handle quitting before first message
             st.session_state.messages = [{"role": "system", "content": config.SYSTEM_PROMPT},
                                          {"role": "assistant", "content": quit_message}]
        # Final save, indicating it's the definitive end
        save_interview_data(
            username=st.session_state.username,
            transcripts_directory=config.TRANSCRIPTS_DIRECTORY,
            times_directory=config.TIMES_DIRECTORY,
            is_final_save=True # Pass flag to format transcript
        )
        st.warning(quit_message)
        st.session_state.current_stage = SURVEY_STAGE # Move stage
        time.sleep(1)
        st.rerun() # Rerun to display survey

    # Display Chat History
    for message in st.session_state.messages:
        if api == "openai" and message["role"] == "system": continue
        # Don't display the raw code message in chat history
        if message["content"] in config.CLOSING_MESSAGES.keys(): continue
        avatar = config.AVATAR_INTERVIEWER if message["role"] == "assistant" else config.AVATAR_RESPONDENT
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    # Initial Interviewer Message
    if not st.session_state.messages:
        try:
            if api == "openai":
                 st.session_state.messages.append({"role": "system", "content": config.SYSTEM_PROMPT})

            with st.chat_message("assistant", avatar=config.AVATAR_INTERVIEWER):
                message_placeholder = st.empty()
                message_interviewer = ""
                api_kwargs = { "model": config.MODEL, "messages": st.session_state.messages, "max_tokens": config.MAX_OUTPUT_TOKENS, "stream": True }
                if api == "anthropic":
                    api_kwargs["system"] = config.SYSTEM_PROMPT
                    # Provide initial user message if needed for Anthropic when history is empty
                    if not any(m['role'] == 'user' for m in api_kwargs["messages"]):
                         api_kwargs["messages"] = [{"role": "user", "content": "Please begin the interview."}]
                if config.TEMPERATURE is not None: api_kwargs["temperature"] = config.TEMPERATURE

                if api == "openai":
                    stream = client.chat.completions.create(**api_kwargs)
                    message_interviewer = st.write_stream(stream)
                elif api == "anthropic":
                     with client.messages.stream(**api_kwargs) as stream:
                         for text_delta in stream.text_stream:
                             if text_delta is not None:
                                 message_interviewer += text_delta; message_placeholder.markdown(message_interviewer + "▌")
                     message_placeholder.markdown(message_interviewer)

            # Store the first message
            st.session_state.messages.append({"role": "assistant", "content": message_interviewer})

            # Store first backup
            if st.session_state.start_time_file_names:
                 backup_suffix = f"_backup_started_{st.session_state.start_time_file_names}"
                 save_interview_data(username=st.session_state.username, transcripts_directory=config.BACKUPS_DIRECTORY,
                                     times_directory=config.BACKUPS_DIRECTORY, file_name_addition_transcript=backup_suffix,
                                     file_name_addition_time=backup_suffix, is_final_save=False) # Not final save
            time.sleep(0.1); st.rerun() # Rerun to display cleanly

        except Exception as e:
            st.error(f"Failed to get initial message from API: {e}"); st.stop()

    # Main Chat Interaction Logic
    if prompt := st.chat_input("Your response..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar=config.AVATAR_RESPONDENT):
            st.markdown(prompt)

        try:
            with st.chat_message("assistant", avatar=config.AVATAR_INTERVIEWER):
                message_placeholder = st.empty()
                message_interviewer = "" # Displayed content
                full_response_content = "" # Full stream, including potential code
                api_kwargs = { "model": config.MODEL, "messages": st.session_state.messages, "max_tokens": config.MAX_OUTPUT_TOKENS, "stream": True }
                if api == "anthropic": api_kwargs["system"] = config.SYSTEM_PROMPT
                if config.TEMPERATURE is not None: api_kwargs["temperature"] = config.TEMPERATURE

                stream_closed = False; detected_code = None
                # Streaming Logic to detect closing code
                if api == "openai":
                    stream = client.chat.completions.create(**api_kwargs)
                    for chunk in stream:
                        text_delta = chunk.choices[0].delta.content
                        if text_delta:
                            full_response_content += text_delta
                            for code in config.CLOSING_MESSAGES.keys():
                                if code == full_response_content.strip(): # Check if stream ONLY contains code
                                    detected_code = code; message_interviewer = full_response_content.replace(code, "").strip()
                                    if not message_interviewer: message_placeholder.empty()
                                    else: message_placeholder.markdown(message_interviewer) # Show preceding text
                                    stream.close(); stream_closed = True; break
                            if stream_closed: break
                            message_interviewer = full_response_content; message_placeholder.markdown(message_interviewer + "▌")
                    if not stream_closed: message_placeholder.markdown(message_interviewer) # Final display
                elif api == "anthropic":
                     with client.messages.stream(**api_kwargs) as stream:
                        for text_delta in stream.text_stream:
                            if text_delta is not None:
                                full_response_content += text_delta
                                for code in config.CLOSING_MESSAGES.keys():
                                    if code == full_response_content.strip():
                                        detected_code = code; message_interviewer = full_response_content.replace(code,"").strip()
                                        if not message_interviewer: message_placeholder.empty()
                                        else: message_placeholder.markdown(message_interviewer)
                                        stream_closed = True; break
                                if stream_closed: break
                                message_interviewer = full_response_content; message_placeholder.markdown(message_interviewer + "▌")
                     if not stream_closed: message_placeholder.markdown(message_interviewer)

                # Store the full assistant response (including potential code)
                st.session_state.messages.append({"role": "assistant", "content": full_response_content.strip()})

                # Process if closing code detected
                if detected_code:
                    st.session_state.interview_active = False
                    st.session_state.interview_completed_flag = True
                    closing_message_display = config.CLOSING_MESSAGES[detected_code]
                    # Final save - Pass flag to format transcript
                    save_interview_data(
                        username=st.session_state.username,
                        transcripts_directory=config.TRANSCRIPTS_DIRECTORY,
                        times_directory=config.TIMES_DIRECTORY,
                        is_final_save=True # Pass the flag
                    )
                    st.success(closing_message_display) # Show user-friendly message
                    st.session_state.current_stage = SURVEY_STAGE # Change stage
                    time.sleep(2)
                    st.rerun() # Rerun to display survey stage

                else: # Interview continues, save backup
                     try:
                         if st.session_state.start_time_file_names:
                             backup_suffix = f"_backup_inprogress_{st.session_state.start_time_file_names}"
                             save_interview_data(username=st.session_state.username, transcripts_directory=config.BACKUPS_DIRECTORY,
                                                 times_directory=config.BACKUPS_DIRECTORY, file_name_addition_transcript=backup_suffix,
                                                 file_name_addition_time=backup_suffix, is_final_save=False) # Not final
                     except Exception as backup_e:
                         print(f"Warning: Backup failed - {backup_e}")

        except Exception as e:
            st.error(f"An error occurred during the interview chat: {e}")


# --- Section 2: Survey Stage ---
elif st.session_state.current_stage == SURVEY_STAGE:
    st.title("Part 2: Survey")
    st.info(f"Thank you {username}, please answer a few final questions.")

    # Define Survey Options
    age_options = ["Select...", "Under 18"] + [str(i) for i in range(18, 36)] + ["Older than 35"]
    gender_options = ["Select...", "Male", "Female", "Non-binary", "Prefer not to say"]
    major_options = ["Select...", "Computer Science", "Engineering (Other)", "Business", "Humanities", "Social Sciences", "Natural Sciences", "Arts", "Health Sciences", "Other", "Not Applicable"]
    year_options = ["Select...", "1st Year Undergraduate", "2nd Year Undergraduate", "3rd Year Undergraduate", "4th+ Year Undergraduate", "Graduate Student", "Postgraduate/Doctoral", "Not a Student"]
    gpa_values = np.round(np.arange(5.0, 10.01, 0.1), 1)
    gpa_options = ["Select...", "Below 5.0"] + [f"{gpa:.1f}" for gpa in gpa_values] + ["Prefer not to say / Not applicable"] # Added option
    ai_freq_options = ["Select...", "Frequently (Daily/Weekly)", "Occasionally (Monthly)", "Rarely (Few times a year)", "Never", "Unsure"]

    # Create the Form
    with st.form("survey_form"):
        st.subheader("Demographic Information")
        age = st.selectbox("What is your age?", age_options, key="age")
        gender = st.selectbox("What is your gender?", gender_options, key="gender")
        major = st.selectbox("What is your primary field of study (if applicable)?", major_options, key="major")
        year_of_study = st.selectbox("What is your current year of study (if applicable)?", year_options, key="year")
        gpa = st.selectbox("What is your approximate current GPA (or equivalent)?", gpa_options, key="gpa")

        st.subheader("AI Usage")
        ai_frequency = st.selectbox("How often do you use AI tools (like ChatGPT, Copilot, etc.) for study or work?", ai_freq_options, key="ai_frequency")
        ai_model = st.text_input("If you know, which AI model(s) do you typically use? (e.g., ChatGPT 3.5/4, Claude, Gemini, Copilot)", key="ai_model")

        submitted = st.form_submit_button("Submit Survey Responses")

    # Handle Form Submission
    if submitted:
        # Validation (check all select boxes)
        if (age == "Select..." or
            gender == "Select..." or
            major == "Select..." or
            year_of_study == "Select..." or
            gpa == "Select..." or
            ai_frequency == "Select..."):
            st.warning("Please answer all dropdown questions before submitting.")
        else:
            # Collect responses
            survey_responses = {
                "age": age,
                "gender": gender,
                "major": major,
                "year": year_of_study, # Key from widget
                "gpa": gpa,
                "ai_frequency": ai_frequency,
                "ai_model": ai_model,
            }

            # Call the main save function (utils handles GSheet/flag file)
            save_successful = save_survey_data(username, survey_responses)

            if save_successful:
                st.session_state.survey_completed_flag = True
                st.session_state.current_stage = COMPLETED_STAGE
                st.success("Survey submitted successfully! Thank you for your participation.")
                st.balloons()
                time.sleep(3)
                st.rerun() # Rerun to show completed stage
            else:
                # Error is usually shown within save_survey_data_to_gsheet
                pass


# --- Section 3: Completed Stage ---
elif st.session_state.current_stage == COMPLETED_STAGE:
    st.title("Thank You!")
    st.success("You have completed the interview and the survey. Your contribution is greatly appreciated!")
    st.markdown("You may now close this window.")


# --- Fallback ---
else:
    st.error("An unexpected state was reached. Please refresh or contact support.")
    print(f"Error: Unexpected session state stage: {st.session_state.get('current_stage')}")