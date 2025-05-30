import streamlit as st
import pymongo
import pandas as pd
import datetime
import numpy as np
import plotly.express as px
from textblob import TextBlob
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# MongoDB Setup
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["telecom_db"]
network_col = db["network_performance"]
outage_col = db["outages"]
feedback_col = db["customer_feedback"]
tickets_col = db["support_tickets"]

st.set_page_config(page_title="Telecom Network Dashboard", layout="wide")
st.title("📡 Telecom Network Dashboard")

menu = st.sidebar.selectbox("Navigate", ["📊 Network Metrics", "📍 Outage Map", "🗣️ Feedback", "🎫 Support Tickets", "⚙️ Admin Panel"])

# 1. Network Metrics
if menu == "📊 Network Metrics":
    st.header("📈 Network Performance Overview")

    data = pd.DataFrame(list(network_col.find()))
    if data.empty:
        st.warning("No data available.")
    else:
        data["date"] = pd.to_datetime(data["date"])
        region = st.selectbox("Select Region", data["region"].unique())
        filtered = data[data["region"] == region].sort_values("date")

        # Date range filter
        start_date, end_date = st.date_input("Select Date Range", [filtered["date"].min(), filtered["date"].max()])
        filtered = filtered[(filtered["date"] >= pd.to_datetime(start_date)) & (filtered["date"] <= pd.to_datetime(end_date))]

        # Metrics summary
        col1, col2, col3 = st.columns(3)
        col1.metric("Avg Uptime (%)", f"{filtered['uptime'].mean():.2f}")
        col2.metric("Avg Latency (ms)", f"{filtered['latency_ms'].mean():.2f}")
        col3.metric("Avg Packet Loss (%)", f"{filtered['packet_loss_percent'].mean():.2f}")

        # Charts
        st.line_chart(filtered.set_index("date")["uptime"])
        st.line_chart(filtered.set_index("date")["latency_ms"])
        st.line_chart(filtered.set_index("date")["packet_loss_percent"])

# 2. Outage Map
elif menu == "📍 Outage Map":
    st.header("📍 Network Outages by Location")
    outages = list(outage_col.find({"resolved": False}))
    if outages:
        df = pd.DataFrame(outages)
        severity_filter = st.multiselect("Filter by Severity", options=df["severity"].unique(), default=list(df["severity"].unique()))
        df = df[df["severity"].isin(severity_filter)]

        fig = px.scatter_mapbox(df, lat="lat", lon="lon", color="severity", hover_name="region",
                                mapbox_style="open-street-map", zoom=3, height=500)
        st.plotly_chart(fig)
        st.dataframe(df[["region", "severity", "reported_at"]])
    else:
        st.success("✅ No active outages currently.")

# 3. Feedback
elif menu == "🗣️ Feedback":
    st.header("🗣️ Submit Customer Feedback")

    with st.form("feedback_form"):
        customer_id = st.text_input("Customer ID")
        region = st.selectbox("Region", ["Delhi", "Mumbai", "Bangalore", "Hyderabad", "Chennai"])
        csat_rating = st.slider("CSAT Rating (1 - 5)", 1, 5)
        feedback_text = st.text_area("Additional Feedback")
        submitted = st.form_submit_button("Submit Feedback")

        if submitted and customer_id:
            feedback_col.insert_one({
                "customer_id": customer_id,
                "region": region,
                "csat_rating": csat_rating,
                "feedback_text": feedback_text,
                "submitted_at": datetime.datetime.utcnow()
            })
            st.success("Thank you for your feedback!")

    st.subheader("📊 CSAT Summary")
    csat_data = pd.DataFrame(list(feedback_col.find()))
    if not csat_data.empty:
        st.bar_chart(csat_data["csat_rating"].value_counts().sort_index())

        # Sentiment analysis
        csat_data["sentiment"] = csat_data["feedback_text"].apply(lambda x: TextBlob(x).sentiment.polarity if x else 0)
        csat_data["submitted_at"] = pd.to_datetime(csat_data["submitted_at"])
        st.line_chart(csat_data.set_index("submitted_at")["sentiment"].rolling(3).mean())

        # Word cloud
        st.subheader("🧠 Common Feedback Themes")
        text = " ".join(csat_data["feedback_text"].dropna())
        wordcloud = WordCloud(width=800, height=400).generate(text)
        fig, ax = plt.subplots()
        ax.imshow(wordcloud, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig)

# 4. Support Tickets
elif menu == "🎫 Support Tickets":
    st.header("🎫 Submit a Support Ticket")

    with st.form("ticket_form"):
        name = st.text_input("Your Name")
        region = st.selectbox("Region", ["Delhi", "Mumbai", "Bangalore", "Hyderabad", "Chennai"])
        issue = st.text_area("Describe your issue")
        submitted = st.form_submit_button("Submit Ticket")

        if submitted and name and issue:
            tickets_col.insert_one({
                "ticket_id": f"TICKET{np.random.randint(1000,9999)}",
                "name": name,
                "region": region,
                "issue": issue,
                "status": "Open",
                "submitted_at": datetime.datetime.utcnow(),
                "resolved_at": None
            })
            st.success("Ticket submitted successfully!")

    st.subheader("📋 All Tickets")
    tickets = list(tickets_col.find())
    if tickets:
        df = pd.DataFrame(tickets)
        df["submitted_at"] = pd.to_datetime(df["submitted_at"])
        df["is_escalated"] = (datetime.datetime.utcnow() - df["submitted_at"]) > pd.Timedelta(hours=48)

        status_filter = st.selectbox("Filter by Status", ["All", "Open", "Resolved"])
        if status_filter != "All":
            df = df[df["status"] == status_filter]

        st.dataframe(df[["ticket_id", "name", "region", "issue", "status", "submitted_at", "is_escalated"]])
    else:
        st.info("No tickets submitted yet.")

# 5. Admin Panel
elif menu == "⚙️ Admin Panel":
    st.header("⚙️ Admin Panel - Manage Outages and Tickets")

    password = st.text_input("Enter admin password", type="password")
    if password == "admin123":
        st.success("Admin access granted")

        # Mark outages resolved
        st.subheader("Mark an Outage as Resolved")
        open_outages = list(outage_col.find({"resolved": False}))
        if open_outages:
            selected = st.selectbox("Select outage to resolve", [f"{o['region']} at {o['reported_at']}" for o in open_outages])
            if st.button("Mark as Resolved"):
                match = open_outages[[f"{o['region']} at {o['reported_at']}" for o in open_outages].index(selected)]
                outage_col.update_one({"_id": match["_id"]}, {"$set": {"resolved": True}})
                st.success("Outage marked as resolved.")
        else:
            st.info("No unresolved outages.")

        # Add new outage
        st.subheader("📌 Log a New Outage")
        with st.form("new_outage_form"):
            region = st.selectbox("Region", ["Delhi", "Mumbai", "Bangalore", "Hyderabad", "Chennai"], key="admin_outage")
            lat = st.number_input("Latitude")
            lon = st.number_input("Longitude")
            severity = st.selectbox("Severity", ["Low", "Medium", "High"])
            submitted = st.form_submit_button("Report Outage")
            if submitted:
                outage_col.insert_one({
                    "region": region,
                    "lat": lat,
                    "lon": lon,
                    "severity": severity,
                    "reported_at": datetime.datetime.utcnow(),
                    "resolved": False
                })
                st.success("Outage reported.")

        # Resolve tickets
        st.subheader("Resolve Open Tickets")
        open_tickets = list(tickets_col.find({"status": "Open"}))
        for ticket in open_tickets:
            with st.expander(f"{ticket['ticket_id']} - {ticket['issue']}"):
                if st.button(f"Mark {ticket['ticket_id']} as Resolved"):
                    tickets_col.update_one({"_id": ticket["_id"]}, {
                        "$set": {"status": "Resolved", "resolved_at": datetime.datetime.utcnow()}
                    })
                    st.success(f"Ticket {ticket['ticket_id']} resolved.")

        # Search ticket by ID
        st.subheader("🔍 Search Ticket")
        search_id = st.text_input("Search Ticket by ID")
        if search_id:
            ticket = tickets_col.find_one({"ticket_id": search_id})
            if ticket:
                st.write(ticket)
                if st.button("Mark Searched Ticket as Resolved"):
                    tickets_col.update_one({"_id": ticket["_id"]}, {
                        "$set": {"status": "Resolved", "resolved_at": datetime.datetime.utcnow()}
                    })
                    st.success("Ticket resolved.")
            else:
                st.warning("Ticket not found.")
    else:
        st.warning("Incorrect password.")
