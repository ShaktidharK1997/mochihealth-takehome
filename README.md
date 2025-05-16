# Mood of the Queue - Mochi Health Takehome

Hey there! So for my take-home, I built a little Streamlit app to track the mood/sentiment of support tickets over time. Nothing fancy, but hopefully useful!

## What it does

This app tracks emotional trends in your support queue:

- Log moods with emojis (😊 happy, 😕 confused, 😠 frustrated, 🎉 celebratory)
- Add notes to provide context
- See a daily visualization of mood distribution
- Auto-refreshes every 30 seconds (optional)
- All data stored in a Google Sheet using a service account

## Setup 

I've set it up using Streamlit Cloud Free version. Check it out at https://mochihealth-takehome-h5uj4gtmrkusegeujbbjnl.streamlit.app/

You can also run it locally by cloning this repo and using Docker-compose. 

## Technical bits

- Built with Streamlit + Pandas + Google Sheets API
- Uses Plotly for visualizations
- Stores credentials securely using Streamlit secrets

## Next steps

With more time, I'd add:
- Historical trends beyond just today 
- Data export features
- More customizable mood options

Lemme know if you need any additional info or have questions!
