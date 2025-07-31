# Import necessary libraries
import streamlit as st
import pandas as pd
import plotly.express as px
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# -----------------------------------------------------------------------------
# Page Configuration (Called only once at the beginning of the script)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="λF Risk Dashboard",
    page_icon="🔺",
    layout="centered",  # 'centered' provides a more focused view, 'wide' is also an option.
    initial_sidebar_state="auto"
)

# -----------------------------------------------------------------------------
# Firebase Connection (Using Streamlit's caching mechanism)
# -----------------------------------------------------------------------------
if not firebase_admin._apps:
    secrets_dict = st.secrets["firebase_key"]
    firebase_creds_copy = dict(secrets_dict)
    firebase_creds_copy['private_key'] = firebase_creds_copy['private_key'].replace('\\n', '\n')
    cred = credentials.Certificate(firebase_creds_copy)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# -----------------------------------------------------------------------------
# Data Fetching Function
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600)  # Cache the data for 10 minutes (600 seconds)
def fetch_lambda_f_data(_db_client):
    """
    Fetches Lambda-F data from Firestore, converts it to a DataFrame, and sorts it.
    The _db_client parameter helps the cache know when to invalidate.
    """
    if _db_client is None:
        return pd.DataFrame() # Return an empty DataFrame
        
    try:
        # Fetch the last 30 records in descending order to get the most recent ones
        docs = _db_client.collection("lambdaF").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(30).stream()
        
        data = []
        for doc in docs:
            doc_data = doc.to_dict()
            data.append({
                "timestamp": doc_data.get("timestamp"),
                "lambda_F": doc_data.get("lambda_F"),
                "status": doc_data.get("status", "N/A")
            })
        
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df = df.dropna(subset=['timestamp', 'lambda_F'])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        # Sort values ascending to plot correctly
        df = df.sort_values(by="timestamp", ascending=True).reset_index(drop=True)
        return df

    except Exception as e:
        st.error(f"An error occurred while fetching data: {e}")
        return pd.DataFrame()

# -----------------------------------------------------------------------------
# Visualization Functions
# -----------------------------------------------------------------------------
def create_time_series_chart(df):
    """
    Creates an interactive time series chart with the given DataFrame.
    """
    if df.empty:
        return None

    fig = px.line(
        df,
        x='timestamp',
        y='lambda_F',
        title="Lambda-F Score Over Time",
        labels={'timestamp': 'Date', 'lambda_F': 'λF Score'},
        markers=True
    )

    # Chart styling and threshold lines
    fig.update_layout(
        xaxis_title="Time",
        yaxis_title="λF Score",
        yaxis_range=[0, 1],
        template="plotly_white", # For a cleaner look
        title_x=0.5 # Center the title
    )
    
    # Threshold lines
    fig.add_hline(y=0.7, line_dash="dot", line_color="red", annotation_text="🚨 Critical Level (0.7)", annotation_position="bottom right")
    fig.add_hline(y=0.5, line_dash="dot", line_color="orange", annotation_text="⚠️ Risk Level (0.5)", annotation_position="bottom right")

    return fig

# -----------------------------------------------------------------------------
# Main Dashboard Interface
# -----------------------------------------------------------------------------

# --- Title ---
st.title("🔺 λF Risk Dashboard")
st.caption(f"Flux Finance | Data last updated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# --- Fetch Data ---
df_history = fetch_lambda_f_data(db)

# --- Main Metrics ---
if not df_history.empty:
    # Get the latest data
    latest_data = df_history.iloc[-1]
    lambda_f_current = latest_data['lambda_F']
    status_current = latest_data['status']

    # Get the previous data point for comparison (if it exists)
    lambda_f_previous = df_history.iloc[-2]['lambda_F'] if len(df_history) > 1 else 0
    delta = lambda_f_current - lambda_f_previous

    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            label="Current λF Score",
            value=f"{lambda_f_current:.3f}",
            delta=f"{delta:.3f} vs. previous day",
            delta_color="inverse" # Positive change is red (bad), negative is green (good)
        )
    
    with col2:
        # Display a colored status text with an icon
        if status_current == "Kritik" or status_current == "Critical":
            st.error(f"**Status: Critical** 🚨")
        elif status_current == "Riskli" or status_current == "Risky":
            st.warning(f"**Status: Risky** ⚠️")
        else:
            st.success(f"**Status: Normal** ✅")
    st.markdown("---")

else:
    st.warning("No historical data available to display yet. Please ensure the simulation is generating data.")


# --- Tabbed Content Area ---
tab1, tab2 = st.tabs(["📈 Time Series Chart", "📄 Data Table"])

with tab1:
    st.subheader("Interactive Chart of λF Scores")
    
    # Create and display the chart
    time_series_chart = create_time_series_chart(df_history)
    if time_series_chart:
        st.plotly_chart(time_series_chart, use_container_width=True)
    else:
        st.info("Not enough data to draw the chart.")

with tab2:
    st.subheader("Historical λF Data (Last 30 records)")
    
    if not df_history.empty:
        # Display the DataFrame in a more readable format
        st.dataframe(
            df_history.sort_values(by="timestamp", ascending=False),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No data table to display.")


# --- Sidebar ---
st.sidebar.header("About the λF Model")
st.sidebar.info(
    """
    **Lambda-F (λF)** is a risk indicator that aims to predict potential instabilities 
    and 'phase transitions' (sudden crashes or overheating) in financial markets 
    by analyzing collective sentiment shifts on social media.
    
    - **0.0 - 0.5 (Normal ✅):** The market is calm.
    - **0.5 - 0.7 (Risky ⚠️):** Uncertainty and volatility are increasing.
    - **0.7 - 1.0 (Critical 🚨):** Social tension is high, increasing the risk of sudden and large price movements.
    """
)
st.sidebar.markdown("---")
if st.sidebar.button('Refresh Data 🔄'):
    # Clear the cache and rerun the script to fetch new data
    st.cache_data.clear()
    st.rerun()
