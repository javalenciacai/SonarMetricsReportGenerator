import streamlit as st
import markdown
import os
from database.schema import check_policy_acceptance, store_policy_acceptance

def load_policies():
    """Load the data policies markdown file"""
    try:
        with open('docs/data_policies.md', 'r') as f:
            return f.read()
    except Exception as e:
        return f"Error loading policies: {str(e)}"

def show_policies():
    """Display data policies in a clean, formatted way"""
    policies = load_policies()
    
    with st.expander("📜 Data Usage Policies & Terms of Service", expanded=False):
        st.markdown("""
        <style>
            .policy-section {
                background-color: #1A1F25;
                padding: 1rem;
                border-radius: 0.5rem;
                border: 1px solid #2D3748;
                margin: 1rem 0;
            }
            .policy-section h1, .policy-section h2 {
                color: #FAFAFA;
            }
            .policy-section h3 {
                color: #A0AEC0;
            }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown(policies)
        
        # Get user token from session state
        user_token = st.session_state.get('sonar_token')
        
        if user_token:
            # Check if policies already accepted
            previously_accepted = check_policy_acceptance(user_token)
            
            # Add acknowledgment checkbox
            if st.checkbox("I have read and agree to the Data Usage Policies and Terms of Service", 
                         value=previously_accepted):
                # Store acceptance in database
                if store_policy_acceptance(user_token):
                    st.session_state.policies_accepted = True
                else:
                    st.error("Failed to store policy acceptance. Please try again.")
                    st.session_state.policies_accepted = False
            else:
                st.session_state.policies_accepted = False
        else:
            st.info("Please enter your SonarCloud token to proceed.")
            st.session_state.policies_accepted = False

def get_policy_acceptance_status(user_token):
    """Get the current policy acceptance status for a user"""
    return check_policy_acceptance(user_token) if user_token else False
