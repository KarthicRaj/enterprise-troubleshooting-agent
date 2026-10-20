
import streamlit as st

from troubleshooting_agent.agent.graph import agent
import html
import markdown
import bleach

from datetime import datetime

st.set_page_config(
    page_title="Troubleshooting Agent",
    page_icon="🔧",
    layout="centered",
)

st.title("Enterprise Troubleshooting Agent")
st.write("Describe an application issue to investigate.")

question = st.text_area(
    "Issue description",
    placeholder="Example: Customers cannot log in. We are seeing HTTP 401 errors.",
    height=150,
)

if st.button("Run Investigation", type="primary"):
    if not question.strip():
        st.warning("Please enter an issue description.")
    else:
        with st.spinner("Investigating the issue..."):
            try:
                result = agent.invoke({"question": question.strip()})
                st.session_state["last_question"] = question.strip()
                st.session_state["last_report"] = result.get(
                                "response", "No report was generated."
                )
                st.subheader("Investigation Report")
                st.markdown(result.get("response", "No report was generated."))
            except Exception:
                st.error(
                    "The investigation failed. Check the application logs "
                    "for details."
                )

if st.session_state.get("last_report"):
    report = st.session_state["last_report"]
    issue = st.session_state.get("last_question", "Not provided")

    report_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Investigation Report</title>
        <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            max-width: 900px;
            margin: 40px auto;
            padding: 0 24px;
            color: #1f2937;
            line-height: 1.65;
            background: #f8fafc;
        }}
        header, main {{
            background: white;
            padding: 24px;
            margin-bottom: 20px;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
        }}
        h1, h2 {{
            color: #0f172a;
        }}
        .meta {{
            color: #64748b;
            font-size: 14px;
        }}
        pre {{
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            font: inherit;
        }}
        @media print {{
            body {{ background: white; margin: 0; }}
            header, main {{ border: none; }}
        }}
        </style>
    </head>
    <body>
        <header>
        <h1>Enterprise Troubleshooting Report</h1>
        <p class="meta">Generated: {datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")}</p>
        <h2>Issue</h2>
        <p>{html.escape(issue)}</p>
        </header>
        <main>
        <h2>Investigation Findings</h2>
            <div class="report-content">
                {bleach.clean(
                    markdown.markdown(
                        html.escape(report),
                        extensions=["extra"]
                    ),
                    tags=[
                        "h1", "h2", "h3", "h4", "p",
                        "ul", "ol", "li", "strong", "em",
                        "blockquote", "code", "pre", "hr",
                        "a", "table", "thead", "tbody",
                        "tr", "th", "td", "br"
                    ],
                    attributes={"a": ["href", "title"]},
                    protocols=["http", "https", "mailto"]
                )}
            </div>
        </main>
    </body>
    </html>
    """

    st.download_button(
        label="Export HTML Report",
        data=report_html,
        file_name="troubleshooting-report.html",
        mime="text/html",
    )
