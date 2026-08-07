"""
Betting Oracle Footer Component

Copy this file to your Streamlit app repository and import it to add consistent branding.
"""

FOOTER_HTML = """
<div style="text-align: center; padding: 20px 0; border-top: 1px solid #e0e0e0; margin-top: 40px;">
    <p style="margin: 0 0 10px 0; font-size: 14px; color: #666; font-family: sans-serif;">
        Powered by <a href="https://www.betting-oracle.com" target="_blank" style="color: #3b82f6; text-decoration: none; font-weight: bold;">Betting Oracle</a>
    </p>
    <p style="margin: 0 0 15px 0; font-size: 12px; color: #888; font-family: sans-serif;">
        Sports Prediction Analytics
    </p>
    <a href="https://www.betting-oracle.com" target="_blank">
        <img src="https://raw.githubusercontent.com/gmalbert/betting-oracle/main/data_files/logo.png"
             alt="Betting Oracle Logo"
             style="height: 60px; width: auto; border: none;">
    </a>
</div>
"""


def add_betting_oracle_footer():
    """
    Add the Betting Oracle footer to your Streamlit app.

    Usage:
        from footer import add_betting_oracle_footer

        # At the end of your app
        add_betting_oracle_footer()
    """
    import streamlit as st
    st.markdown(FOOTER_HTML, unsafe_allow_html=True)


def add_sidebar_logo(width: int = 120):
    """
    Add the WNBA logo (wordmark-free) to the top of the sidebar.

    Used by sub-pages (the main predictions.py shows the full logo in the header).
    Must be called after st.set_page_config() and before other sidebar content.
    """
    import streamlit as st
    st.sidebar.image("data_files/logo_no_words.png", width=width)
