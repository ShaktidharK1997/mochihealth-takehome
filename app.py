import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import plotly.express as px
import time
import json
import base64

st.set_page_config(page_title="Mood of the Queue", layout="wide")
st.title("🧪 Mood of the Queue")
st.subheader("Track the emotional trend of support tickets")

@st.cache_resource
def connect_to_sheets():
    # Get the credentials from st.secrets
    credentials_dict = None
    
    # Try to get from Streamlit secrets
    if 'google_credentials' in st.secrets:
        credentials_dict = st.secrets['google_credentials']
    
    # If not found in secrets, try to get from session state
    elif 'credentials_dict' in st.session_state:
        credentials_dict = st.session_state.credentials_dict
    
    # If still not found, return None to handle the error in the main function
    if not credentials_dict:
        return None, None, None, None
    
    scope = ["https://spreadsheets.google.com/feeds", 
             "https://www.googleapis.com/auth/drive",
             "https://www.googleapis.com/auth/spreadsheets"]
    
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(credentials)
    service_account_email = credentials.service_account_email
    
    # Get spreadsheet name from secrets or use default
    spreadsheet_name = st.secrets.get('spreadsheet_name', 'Mood_of_the_Queue_Data')
    
    try:
        spreadsheet = client.open(spreadsheet_name)
        sheet = spreadsheet.sheet1
        return sheet, spreadsheet, service_account_email, True
    except gspread.exceptions.SpreadsheetNotFound:
        spreadsheet = client.create(spreadsheet_name)
        sheet = spreadsheet.sheet1
        
        sheet.append_row(["Timestamp", "Mood", "Note"])
        return sheet, spreadsheet, service_account_email, False

def share_spreadsheet(spreadsheet, email):
    if email and '@' in email:
        try:
            spreadsheet.share(email, perm_type='user', role='writer')
            return True, None
        except Exception as e:
            return False, str(e)
    return False, "Invalid email format"
    
def log_mood(sheet, mood, note=""):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"Logging mood: {mood} (type: {type(mood)}, length: {len(mood) if isinstance(mood, str) else 'N/A'})")
        
        if not isinstance(mood, str):
            mood = str(mood)
        
        encoded = mood.encode('utf-8')
        decoded = encoded.decode('utf-8')
        print(f"Emoji encoded and decoded: {decoded}")
        
        result = sheet.append_row([timestamp, mood, note])
        print(f"Log result: {result}")
        
        return timestamp, True, None
    except Exception as e:
        print(f"Error logging mood: {str(e)}")
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S"), False, str(e)

def get_today_data(sheet):
    try:
        data = sheet.get_all_records()
        print(f"Retrieved {len(data)} records from sheet")
        
        df = pd.DataFrame(data)
        
        if not df.empty and "Timestamp" in df.columns:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="%Y-%m-%d %H:%M:%S", errors='coerce')
            
            today = datetime.now().strftime("%Y-%m-%d")
            today_data = df[df["Timestamp"].dt.strftime("%Y-%m-%d") == today]
            
            print(f"Found {len(today_data)} records for today ({today})")
            if not today_data.empty:
                print(f"Sample data: {today_data.iloc[0].to_dict()}")
            
            return today_data
        return pd.DataFrame(columns=["Timestamp", "Mood", "Note"])
    except Exception as e:
        print(f"Error getting today's data: {str(e)}")
        st.error(f"Error fetching data: {str(e)}")
        return pd.DataFrame(columns=["Timestamp", "Mood", "Note"])

def display_mood_chart(today_data):
    if not today_data.empty:
        mood_counts = today_data["Mood"].value_counts().reset_index()
        mood_counts.columns = ["Mood", "Count"]
        
        print("Mood counts for chart:")
        print(mood_counts)
        
        fig = px.bar(
            mood_counts, 
            x="Mood", 
            y="Count", 
            title="Today's Mood Distribution",
            color="Mood",
            color_discrete_map={
                "😊": "#76C893",
                "😕": "#FFD166",
                "😠": "#EF476F",
                "🎉": "#118AB2",
            }
        )
        
        fig.update_layout(
            xaxis_title="Mood",
            yaxis_title="Count",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No mood data recorded for today yet.")

def main():
    if 'selected_mood' not in st.session_state:
        st.session_state.selected_mood = None
    
    st.sidebar.title("Setup")
    
    # Check if we have credentials in Streamlit secrets
    has_secrets = 'google_credentials' in st.secrets
    
    # If no secrets are configured, show the credential upload form
    if not has_secrets and 'credentials_dict' not in st.session_state:
        st.sidebar.error("Google credentials not found in Streamlit secrets!")
        st.sidebar.info("Please upload your Google service account credentials file:")
        
        uploaded_file = st.sidebar.file_uploader("Upload your credentials.json file", type=["json"])
        if uploaded_file:
            try:
                # Read and parse the JSON
                credentials_content = uploaded_file.read().decode("utf-8")
                credentials_dict = json.loads(credentials_content)
                # Store in session state
                st.session_state.credentials_dict = credentials_dict
                st.sidebar.success("Credentials uploaded! Refreshing...")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error parsing credentials: {e}")
        
        # Provide alternative to paste JSON
        st.sidebar.markdown("### Or paste your credentials JSON:")
        credentials_json = st.sidebar.text_area("Paste JSON credentials here:", height=100)
        
        if credentials_json:
            try:
                credentials_dict = json.loads(credentials_json)
                st.session_state.credentials_dict = credentials_dict
                st.sidebar.success("Credentials parsed! Refreshing...")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error parsing JSON: {e}")
        
        st.sidebar.markdown("### How to create credentials")
        st.sidebar.markdown("""
        1. Go to [Google Cloud Console](https://console.cloud.google.com/)
        2. Create a new project
        3. Enable Google Sheets API and Google Drive API
        4. Create a service account
        5. Create a JSON key for the service account
        6. Download and upload the JSON key here
        """)
        
        st.warning("Please upload credentials in the sidebar to continue")
        return
    
    if 'sheet_shared' not in st.session_state:
        st.session_state.sheet_shared = False
    if 'share_status_message' not in st.session_state:
        st.session_state.share_status_message = ""
    
    try:
        sheet_info = connect_to_sheets()
        
        # If connect_to_sheets returns None, handle as error
        if sheet_info[0] is None:
            st.error("Failed to connect to Google Sheets: Invalid credentials")
            st.info("Please check your credentials and try again.")
            return
            
        sheet, spreadsheet, service_email, is_existing = sheet_info
        
        st.sidebar.success("Connected to Google Sheets")
        st.sidebar.info(f"Service Account: {service_email}")
        
        sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
        st.sidebar.markdown(f"[Open Spreadsheet]({sheet_url})")
        
        if is_existing:
            st.success(f"Connected to existing Google Sheet")
        else:
            st.info(f"Created new Google Sheet")
        
        st.sidebar.markdown("### Share Spreadsheet")
        st.sidebar.markdown("Share access to view/edit this spreadsheet:")
        
        col1, col2 = st.sidebar.columns([3, 1])
        
        with col1:
            user_email = st.text_input("Email address:", key="email_input")
        
        with col2:
            st.write("")
            share_button = st.button("Share", key="share_btn")
        
        if st.session_state.share_status_message:
            if "Error" in st.session_state.share_status_message:
                st.sidebar.error(st.session_state.share_status_message)
            else:
                st.sidebar.success(st.session_state.share_status_message)
        
        if share_button and user_email:
            success, error = share_spreadsheet(spreadsheet, user_email)
            if success:
                st.session_state.share_status_message = f"Spreadsheet shared with {user_email}"
                st.session_state.sheet_shared = True
            else:
                st.session_state.share_status_message = f"Error sharing spreadsheet: {error}"
            st.rerun() 
        
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        st.info("Please check your credentials and try again.")
        return

    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Log a Mood")
        
        mood_options = ["😊", "😕", "😠", "🎉"]
        mood_descriptions = {
            "😊": "Happy/Satisfied",
            "😕": "Confused/Uncertain",
            "😠": "Frustrated/Angry",
            "🎉": "Celebratory/Excited"
        }
        
        mood_selection = st.radio(
            "Select a mood:",
            mood_options,
            format_func=lambda x: f"{x} - {mood_descriptions[x]}",
            index=None,
            key="mood_radio"
        )
        
        if mood_selection:
            st.session_state.selected_mood = mood_selection
            st.success(f"Selected mood: {mood_selection}")
        
        note = st.text_area("Add a note (optional)", max_chars=100)

        
        if st.button("Submit", disabled=(st.session_state.selected_mood is None), key="submit_direct"):
            mood_to_log = st.session_state.selected_mood
            st.write(f"Submitting mood: {mood_to_log}")
            timestamp, success, error = log_mood(sheet, mood_to_log, note)
            
            if success:
                st.success(f"Mood logged at {timestamp}")
                st.session_state.selected_mood = None 
            else:
                st.error(f"Failed to log mood: {error}")
                st.info("This might be due to permission issues with Google Sheets.")
            
            time.sleep(1)
            st.rerun() 
    
    with col2:
        st.subheader("Today's Mood Visualization")
        
        today_data = get_today_data(sheet)
        
        display_mood_chart(today_data)
        
        if st.checkbox("Auto-refresh (every 30 seconds)"):
            refresh_interval = 30
            st.write(f"Chart will refresh every {refresh_interval} seconds")
            
            progress_bar = st.progress(0)
            for i in range(refresh_interval):
                progress_bar.progress((i + 1) / refresh_interval)
                time.sleep(1)
            
            st.rerun() 
        
        if not today_data.empty:
            st.subheader("Recent Entries")
            recent_data = today_data.sort_values("Timestamp", ascending=False).head(5)
            
            for _, row in recent_data.iterrows():
                time_str = row["Timestamp"].strftime("%H:%M:%S")
                st.write(f"{time_str} - {row['Mood']} - {row['Note']}")

                
if __name__ == "__main__":
    main()