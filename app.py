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
        
        df = pd.DataFrame(data)
        
        if not df.empty and "Timestamp" in df.columns:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="%Y-%m-%d %H:%M:%S", errors='coerce')
            
            today = datetime.now().strftime("%Y-%m-%d")
            today_data = df[df["Timestamp"].dt.strftime("%Y-%m-%d") == today]
            
            return today_data
        return pd.DataFrame(columns=["Timestamp", "Mood", "Note"])
    except Exception as e:
        print(f"Error getting today's data: {str(e)}")
        st.error(f"Error fetching data: {str(e)}")
        return pd.DataFrame(columns=["Timestamp", "Mood", "Note"])

def get_data_for_period(sheet, days):
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty and "Timestamp" in df.columns:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="%Y-%m-%d %H:%M:%S", errors='coerce')
            
            if days > 0:
                cutoff_date = datetime.now() - pd.Timedelta(days=days)
                filtered_data = df[df["Timestamp"] >= cutoff_date]
            else:
                today = datetime.now().strftime("%Y-%m-%d")
                filtered_data = df[df["Timestamp"].dt.strftime("%Y-%m-%d") == today]
            
            return filtered_data
        return pd.DataFrame(columns=["Timestamp", "Mood", "Note"])
    except Exception as e:
        print(f"Error getting data for period: {str(e)}")
        st.error(f"Error fetching data: {str(e)}")
        return pd.DataFrame(columns=["Timestamp", "Mood", "Note"])

def display_mood_chart(data, group_by_day=False):
    if not data.empty:
        if group_by_day:
            # Group by day and mood
            data['Date'] = data['Timestamp'].dt.date
            mood_counts = data.groupby(['Date', 'Mood']).size().reset_index(name='Count')
            
            fig = px.bar(
                mood_counts,
                x="Date",
                y="Count",
                color="Mood",
                title="Mood Distribution Over Time",
                color_discrete_map={
                    "😊": "#76C893",
                    "😕": "#FFD166",
                    "😠": "#EF476F",
                    "🎉": "#118AB2",
                }
            )
        else:
            mood_counts = data["Mood"].value_counts().reset_index()
            mood_counts.columns = ["Mood", "Count"]
            
            fig = px.bar(
                mood_counts,
                x="Mood",
                y="Count",
                title="Mood Distribution",
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
        st.info("No mood data recorded for the selected period.")

def main():
    if 'selected_mood' not in st.session_state:
        st.session_state.selected_mood = None
    if 'refresh_counter' not in st.session_state:
        st.session_state.refresh_counter = 0
    if 'last_refresh_time' not in st.session_state:
        st.session_state.last_refresh_time = datetime.now()
    
    st.sidebar.title("Setup")
    
    # Check if we have credentials in Streamlit secrets
    has_secrets = 'google_credentials' in st.secrets

    if not has_secrets and 'credentials_dict' not in st.session_state:
        st.sidebar.error("Google credentials not found in Streamlit secrets!")
        st.sidebar.info("Please upload your Google service account credentials file:")
        
        # Alternative to paste JSON
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
        st.subheader("Mood trends")
        
        filter_col1, filter_col2 = st.columns([2, 1])
        
        with filter_col1:
            time_period = st.selectbox(
                "Select time period:",
                options=[
                    ("Today", 0),
                    ("Last 3 days", 3),
                    ("Last 7 days", 7),
                    ("Last 30 days", 30)
                ],
                format_func=lambda x: x[0],
                index=0
            )
        
        today_data = get_today_data(sheet)
        
        with filter_col2:
            group_by_day = st.checkbox("Group by day", value=False)
        
        
        # Get data for selected period
        filtered_data = get_data_for_period(sheet, time_period[1])
        
        display_mood_chart(filtered_data, group_by_day)
        
        # Auto-refresh feature
        auto_refresh = st.checkbox("Auto-refresh", value=False)
        
        if auto_refresh:
            refresh_interval = st.slider("Refresh interval (seconds)", 5, 30, 60)
            
            # progress bar for the refresh interval
            refresh_progress = st.progress(0)
            
            # If this is a fresh render or we've completed a cycle
            if "last_refresh_time" not in st.session_state or \
               (datetime.now() - st.session_state.last_refresh_time).total_seconds() >= refresh_interval:
                
                # Reset the timer and refresh
                st.session_state.last_refresh_time = datetime.now()
                st.session_state.refresh_counter += 1
                refresh_progress.progress(0)
                
                time.sleep(0.1)
                st.rerun()
            else:
                # Update progress based on elapsed time
                elapsed = (datetime.now() - st.session_state.last_refresh_time).total_seconds()
                progress = min(elapsed / refresh_interval, 1.0)
                refresh_progress.progress(progress)
                
                # Rerun if not at 100% yet
                if progress < 1.0:
                    time.sleep(0.5)
                    st.rerun()
        
        # Show recent entries
        if not filtered_data.empty:
            st.subheader("Live Feed")
            recent_data = filtered_data.sort_values("Timestamp", ascending=False).head(5)
            
            for _, row in recent_data.iterrows():
                time_str = row["Timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                st.write(f"{time_str} - {row['Mood']} - {row['Note']}")

if __name__ == "__main__":
    main()