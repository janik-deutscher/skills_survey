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
    st.title("Welcome")

    # --- REVISED INTRO TEXT ---
    st.markdown(f"""
    Hi there, thanks for your interest in this research project!

    My name is Janik Deutscher, and I'm a PhD Candidate at UPF. For my research, I'm exploring how university students like you think about valuable skills for the future, the role of Artificial Intelligence (AI), and how these views connect to educational choices.

    To understand your perspective, this study involves an **interview conducted by an AI assistant** followed by a short survey.

    Before we begin, please carefully read the **Information Sheet & Consent Form** below.
    """)
    # --- END REVISED INTRO TEXT ---

    st.markdown("---") # Separator

    # --- REVISED DATA PROTECTION INFO with MARKDOWN BULLETS ---
    st.subheader("Information Sheet & Consent Form")
    st.markdown("""
**Study Title:** Student Perspectives on Skills, Careers, and Artificial Intelligence \n
**Researcher:** Janik Deutscher (janik.deutscher@upf.edu), PhD Candidate, Universitat Pompeu Fabra

**Please read the following information carefully before deciding to participate:**

**1. Purpose of the Research:**
*   This study is part of a PhD research project aiming to understand how university students perceive valuable skills for their future careers, how the rise of Artificial Intelligence (AI) might influence these views, and how this connects to educational choices.

**2. What Participation Involves:**
*   If you agree to participate, you will engage in:
    *   An interview conducted via text chat with an **AI assistant**. The AI will ask you open-ended questions about your career aspirations, skill perceptions, educational choices, and views on AI.
    *   A **short survey** following the interview with some additional questions.
*   The estimated total time commitment is approximately **30-40 minutes**.

**3. Privacy, Anonymity, and API Usage:**
*   Your privacy is protected. No directly identifiable information (like your name, email, or address) will be collected.
*   **AI Interview Data Handling:** To enable the AI assistant to converse with you, your typed responses during the interview will be sent via a secure Application Programming Interface (API) to the AI service provider (OpenAI, for the GPT model used in this study). This is done solely to generate the AI's replies in real-time.
*   **Data Use by AI Provider:** Based on the current policies of major AI providers like OpenAI for API usage, data submitted through the API is **not used to train their AI models**.
*   **Research Data:** The research team only receives the interview transcript (your responses and the AI's questions). During data analysis, this transcript and your survey answers will be linked to a **numerical code**, not to any other identifier.
*   **Anonymization:** Any potentially identifying details mentioned during the interview (e.g., specific names, unique places) will be **removed or pseudonymized** in the transcripts before analysis or publication.

**4. Data Storage and Use:**
*   Anonymized research data (transcripts and survey responses linked to numerical codes) will be stored securely on UPF servers.
*   Data will be kept for the duration of the PhD project and up to two years after its finalization for scientific validation, according to UPF regulations.
*   Anonymized data may be reused for other related research projects or archived/published in a public repository in the future.

**5. Voluntary Participation and Withdrawal:**
*   Your participation is entirely **voluntary**.
*   You can **stop the interview at any time** without penalty by using the "Quit" button.
*   You may choose **not to answer any specific question** in the survey.
*   Once your data is submitted and anonymized, removing your specific responses may be difficult. However, if you have concerns after participation, you can contact Janik Deutscher (janik.deutscher@upf.edu) with your session UserID (if provided/known).

**6. Risks and Benefits:**
*   Participating in this study involves risks **no greater than those encountered in everyday life** (e.g., reflecting on your opinions).
*   There are **no direct benefits** guaranteed to you from participating, although your responses will contribute valuable insights to research on education and career preparation.

**7. Contact Information:**
*   If you have questions about this study, please contact the researcher, **Janik Deutscher (janik.deutscher@upf.edu)**.
*   If you have concerns about this study or your rights as a participant, you may contact **UPF’s Institutional Committee for the Ethical Review of Projects (CIREP)** by phone (+34 935 422 186) or email (secretaria.cirep@upf.edu). CIREP is independent of the research team and treats inquiries confidentially.

**8. GDPR Information (Data Protection):**
*   In accordance with the General Data Protection Regulation (GDPR) 2016/679 (EU), we provide the following:
    *   **Data Controller:** Universitat Pompeu Fabra. Pl. de la Mercè, 10-12. 08002 Barcelona. Tel. +34 935 422 000.
    *   **Data Protection Officer (DPO):** Contact via email at dpd@upf.edu.
    *   **Purposes of Processing:** Carrying out the research project described above. Anonymized research data will be kept as described in section 4. The temporary processing of interview data by the AI provider via API is described in section 3.
    *   **Legal Basis:** Your explicit consent. You can withdraw consent at any time (though data withdrawal post-submission may be limited as explained above).
    *   **Your Rights:** You have the right to access your data; request rectification, deletion, or portability (in certain cases); object to processing; or request limitation. Procedures are described at www.upf.edu/web/proteccio-dades/drets. Contact the DPO (dpd@upf.edu) for queries. If unsatisfied, you may contact the Catalan Data Protection Authority (apdcat.gencat.cat).
    """)
    # --- END REVISED DATA PROTECTION INFO ---

    # --- Consent Checkbox ---
    consent = st.checkbox("I confirm that I have read and understood the information sheet above, including the information about how the AI interview works. I am 18 years or older, and I voluntarily consent to participate in this study.", key="consent_checkbox", value=st.session_state.consent_given) # Reflect current state

    # Store consent checkbox state immediately
    st.session_state.consent_given = consent

    # --- Start Button (Disabled until consent is given) ---
    if st.button("Start Interview", key="start_interview_btn", disabled=not st.session_state.consent_given):
        if st.session_state.consent_given: # Double check state just before proceeding
            st.session_state.welcome_shown = True
            st.session_state.current_stage = INTERVIEW_STAGE # Explicitly set next stage
            st.rerun()
    elif not st.session_state.consent_given:
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
    st.info(f"Thank you {username}, please answer a few final questions.") # Removed username display for better privacy practice if needed
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