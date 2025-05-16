import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import plotly.express as px
import time
import json

st.set_page_config(page_title="Mood of the Queue", layout="wide")
st.title("🧪 Mood of the Queue")
st.subheader("Track the emotional trend of support tickets")

@st.cache_resource
def connect_to_sheets():
    # Get the credentials from st.secrets only
    if 'google_credentials' not in st.secrets or 'spreadsheet_name' not in st.secrets:
        return None, None, None, None
    
    credentials_dict = st.secrets['google_credentials']
    
    scope = ["https://spreadsheets.google.com/feeds", 
             "https://www.googleapis.com/auth/drive",
             "https://www.googleapis.com/auth/spreadsheets"]
    
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(credentials)
    service_account_email = credentials.service_account_email
    
    # Get spreadsheet name from secrets
    spreadsheet_name = st.secrets['spreadsheet_name']
    
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
        
        if not isinstance(mood, str):
            mood = str(mood)
        
        encoded = mood.encode('utf-8')
        decoded = encoded.decode('utf-8')
        
        result = sheet.append_row([timestamp, mood, note])
        
        return timestamp, True, None
    except Exception as e:
        print(f"Error logging mood: {str(e)}")
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S"), False, str(e)

def get_data(sheet, days=0):
    try:
        data = sheet.get_all_records()
        
        df = pd.DataFrame(data)
        
        if not df.empty and "Timestamp" in df.columns:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="%Y-%m-%d %H:%M:%S", errors='coerce')
            
            if days == 0:  # Today only
                today = datetime.now().strftime("%Y-%m-%d")
                filtered_data = df[df["Timestamp"].dt.strftime("%Y-%m-%d") == today]
            else:
                start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
                filtered_data = df[df["Timestamp"].dt.strftime("%Y-%m-%d") >= start_date]
            
            return filtered_data
        return pd.DataFrame(columns=["Timestamp", "Mood", "Note"])
    except Exception as e:
        print(f"Error getting data: {str(e)}")
        st.error(f"Error fetching data: {str(e)}")
        return pd.DataFrame(columns=["Timestamp", "Mood", "Note"])

def display_mood_chart(data, group_by_day=False):
    if not data.empty:
        if group_by_day:
            # Add a date column without time
            data['Date'] = data['Timestamp'].dt.strftime('%Y-%m-%d')
            
            # Group by date and mood, count occurrences
            mood_counts = data.groupby(['Date', 'Mood']).size().reset_index(name='Count')
            
            # Create a stacked bar chart
            fig = px.bar(
                mood_counts,
                x="Date",
                y="Count",
                color="Mood",
                title="Mood Distribution by Day",
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
            xaxis_title="Mood" if not group_by_day else "Date",
            yaxis_title="Count",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No mood data recorded for the selected period.")

def main():
    if 'selected_mood' not in st.session_state:
        st.session_state.selected_mood = None
    
    st.sidebar.title("Setup")
    
    # Check if we have credentials in Streamlit secrets
    has_secrets = 'google_credentials' in st.secrets and 'spreadsheet_name' in st.secrets
    
    # If no secrets are configured, show error message
    if not has_secrets:
        st.error("Google credentials and/or spreadsheet name not found in Streamlit secrets!")
        st.info("""
        Please add the following to your Streamlit secrets:
        ```
        [secrets]
        google_credentials = {...} # Your service account JSON
        spreadsheet_name = "Mood_of_the_Queue_Data"
        ```
        Learn more about Streamlit secrets at: https://docs.streamlit.io/streamlit-cloud/get-started/deploy-an-app/connect-to-data-sources/secrets-management
        """)
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
            st.info("Please check your credentials in Streamlit secrets and try again.")
            return
            
        sheet, spreadsheet, service_email, is_existing = sheet_info
        
        st.sidebar.success("Connected to Google Sheets")
        st.sidebar.info(f"Service Account: {service_email}")
        
        sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
        st.sidebar.markdown(f"[Open Spreadsheet]({sheet_url})")
        
        if is_existing:
            st.sidebar.success(f"Connected to existing Google Sheet")
        else:
            st.sidebar.info(f"Created new Google Sheet")
        
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
        st.info("Please check your credentials in Streamlit secrets and try again.")
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
        st.subheader("Mood Visualization")
        
        # Add filters for date range and grouping
        filter_col1, filter_col2 = st.columns(2)
        
        with filter_col1:
            days_filter = st.selectbox(
                "Select time period:", 
                options=[0, 7, 30, 90], 
                format_func=lambda x: "Today" if x == 0 else f"Last {x} days",
                key="days_filter"
            )
        
        with filter_col2:
            group_by_day = st.checkbox("Group by day", value=False, key="group_by_day")
            group_by_day_disabled = days_filter == 0
            
            if group_by_day_disabled and group_by_day:
                st.warning("Grouping by day only works when viewing multiple days")
                group_by_day = False
        
        data = get_data(sheet, days=days_filter)
        
        display_mood_chart(data, group_by_day=group_by_day and days_filter > 0)
        
        if st.checkbox("Auto-refresh (every 30 seconds)"):
            refresh_interval = 30
            st.write(f"Chart will refresh every {refresh_interval} seconds")
            
            progress_bar = st.progress(0)
            for i in range(refresh_interval):
                progress_bar.progress((i + 1) / refresh_interval)
                time.sleep(1)
            
            st.rerun() 
        
        if not data.empty:
            st.subheader("Recent Entries")
            recent_data = data.sort_values("Timestamp", ascending=False).head(5)
            
            for _, row in recent_data.iterrows():
                time_str = row["Timestamp"].strftime("%H:%M:%S")
                date_str = row["Timestamp"].strftime("%Y-%m-%d")
                st.write(f"{date_str} {time_str} - {row['Mood']} - {row['Note']}")

                
if __name__ == "__main__":
    main()
