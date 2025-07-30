import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime


if not firebase_admin._apps:
    secrets_dict = st.secrets["firebase_key"]
    firebase_creds_copy = dict(secrets_dict)
    firebase_creds_copy['private_key'] = firebase_creds_copy['private_key'].replace('\\n', '\n')
    cred = credentials.Certificate(firebase_creds_copy)
    firebase_admin.initialize_app(cred)

db = firestore.client()


@st.cache_data(ttl=600)
def fetch_lambdaF_history():
    docs = db.collection("lambdaF").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(30).stream()
    
    data = []
    for doc in docs:
        doc_data = doc.to_dict()

        scores = doc_data.get("source_scores", {})
        
        data.append({
            "timestamp": doc_data.get("timestamp"),
            "lambda_F": doc_data.get("lambda_F"),
            "fearAndGreed": scores.get("fearAndGreed"),
            "redditHype": scores.get("redditHype"),
            "volumeSpike": scores.get("volumeSpike")
        })
    
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df = df.dropna(subset=['timestamp'])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(by="timestamp", ascending=True)
    return df

# --- Dashboard Arayüzü ---
st.set_page_config(layout="wide", page_title="Lambda-F Risk Indicator")

st.title("λF Real-Time Market Uncertainty Indicator")
st.markdown("It aims to predict phase transitions such as crises or bubbles by measuring collective sentiment and hype in the markets.")

df_history = fetch_lambdaF_history()

if df_history.empty:
    st.warning("Data could not be retrieved from Firestore or no data is available yet.")
else:

    latest_data = df_history.iloc[-1]
    lambda_F = latest_data["lambda_F"]


    st.markdown("---")
    

    st.header(f"Current λF Value: `{lambda_F:.3f}`")
    if lambda_F > 0.7:
        st.error("🚨 CRITICAL AREA: Social and market turmoil is very high. Risk of overheating.")
    elif lambda_F > 0.5:
        st.warning("⚠️ RISK AREA: Uncertainty and volatility risk are increasing.")
    else:
        st.success("✅ NORMAL LEVEL: The market appears stable.")

    st.subheader("λF Component Scores (0-100)")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label=" General Market Sentiment",
            value=f"{latest_data['fearAndGreed']:.0f}",
            help="Fear and Greed Index. Low values indicate fear, high values indicate greed."
        )
    with col2:
        st.metric(
            label="💬 Social Media Hype",
            value=f"{latest_data['redditHype']:.0f}",
            help="Social enthusiasm level based on the number of keywords on Reddit."
        )
    with col3:
        st.metric(
            label="📈 Market Activity",
            value=f"{latest_data['volumeSpike']:.0f}",
            help="A score that measures sudden increases in transaction volume."
        )


    st.markdown("---")
    st.subheader("📊 Change in λF over Time and Contribution of Components")


    df_history['fng_contrib'] = (df_history['fearAndGreed'] / 100) * 0.4
    df_history['reddit_contrib'] = (df_history['redditHype'] / 100) * 0.3
    df_history['volume_contrib'] = (df_history['volumeSpike'] / 100) * 0.3
    

    fig, ax = plt.subplots(figsize=(12, 6))
    

    ax.stackplot(
        df_history['timestamp'],
        df_history['fng_contrib'],
        df_history['reddit_contrib'],
        df_history['volume_contrib'],
        labels=['Market Sentiment (%40)', 'Social Hype (%30)', 'Market Activity (%30)'],
        alpha=0.7
    )
    
    
    ax.plot(df_history['timestamp'], df_history['lambda_F'], color='black', linewidth=2, linestyle='--', label='Total λF Value')


    ax.axhline(y=0.5, color='darkorange', linestyle='--', label='⚠️ Risk Threshold (0.5)')
    ax.axhline(y=0.7, color='red', linestyle='--', label='🚨 Critical Threshold (0.7)')
    

    ax.set_title("Time Series Contribution of λF Components", fontsize=16)
    ax.set_xlabel("Time")
    ax.set_ylabel("λF Value and Contribution")
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, max(1.0, df_history['lambda_F'].max() * 1.1))

    st.pyplot(fig)

    st.markdown("---")
    with st.expander("View Raw Data for the Last 30 Days"):
        st.dataframe(df_history)
