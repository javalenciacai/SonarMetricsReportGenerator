import streamlit as st
from database.schema import (
    create_tag, get_all_tags, get_project_tags,
    add_tag_to_project, remove_tag_from_project, delete_tag
)
import time

def render_tag_badge(tag, on_remove=None):
    """Render a styled tag badge"""
    html = f"""
        <div style="
            display: inline-flex;
            align-items: center;
            background-color: {tag['color']};
            color: {'#000' if tag['color'] in ['#FFFFFF', '#FFE4E1', '#E0FFFF', '#F0F8FF'] else '#FFF'};
            padding: 2px 8px;
            border-radius: 12px;
            margin: 2px;
            font-size: 0.8rem;">
            {tag['name']}
        </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    if on_remove:
        st.button("×", key=f"remove_tag_{tag['id']}", on_click=on_remove, args=(tag['id'],))

def handle_tag_addition(repo_key, tag_id):
    """Handle tag addition with proper state management and feedback"""
    if not tag_id:
        st.error("Please select a tag first")
        return False
    
    with st.spinner("Adding tag..."):
        result = add_tag_to_project(repo_key, tag_id)
        
        if result["success"]:
            if result["status"] == "already_exists":
                st.warning("Tag already assigned to this project")
            else:
                st.success("Tag added successfully")
            # Clear selection after successful addition
            st.session_state.selected_tag_id = None
            return True
        else:
            if result["status"] == "not_found":
                st.error("Project not found")
            else:
                st.error(f"Failed to add tag: {result.get('message', 'Unknown error')}")
            return False

def display_project_tags(repo_key):
    """Display and manage tags for a specific project"""
    st.markdown("### 🏷️ Project Tags")
    
    # Initialize session states
    if 'tag_creation_status' not in st.session_state:
        st.session_state.tag_creation_status = None
    if 'tag_creation_message' not in st.session_state:
        st.session_state.tag_creation_message = None
    if 'selected_tag_id' not in st.session_state:
        st.session_state.selected_tag_id = None
    if 'adding_tag' not in st.session_state:
        st.session_state.adding_tag = False
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        current_tags = get_project_tags(repo_key)
        all_tags = get_all_tags()
        
        if current_tags:
            st.markdown("Current tags:")
            for tag in current_tags:
                render_tag_badge(tag, lambda tag_id: remove_tag_from_project(repo_key, tag_id))
        else:
            st.info("No tags assigned to this project")
    
    with col2:
        with st.expander("➕ Add Tag", expanded=True):
            # Add existing tag
            available_tags = [tag for tag in all_tags if tag['id'] not in [t['id'] for t in current_tags]]
            
            if available_tags:
                # Use session state for tag selection
                selected_tag = st.selectbox(
                    "Select tag",
                    options=available_tags,
                    format_func=lambda x: x['name'],
                    key="tag_selector",
                    index=None
                )
                
                # Add tag button with loading state
                if st.button("Add Selected Tag", 
                           disabled=st.session_state.adding_tag or not selected_tag,
                           key="add_tag_button"):
                    st.session_state.adding_tag = True
                    if selected_tag:
                        if handle_tag_addition(repo_key, selected_tag['id']):
                            st.session_state.tag_selector = None  # Reset selection
                    st.session_state.adding_tag = False
                    st.rerun()
            else:
                st.info("No available tags to add")
            
            # Create new tag section
            st.markdown("---")
            st.markdown("##### Create New Tag")
            
            with st.form("create_tag_form"):
                new_tag_name = st.text_input("Tag name")
                new_tag_color = st.color_picker("Tag color", value='#808080')
                submit_button = st.form_submit_button("Create Tag")
                
                if submit_button:
                    if not new_tag_name:
                        st.error("Please enter a tag name")
                    else:
                        with st.spinner("Creating tag..."):
                            tag_id, message = create_tag(new_tag_name, new_tag_color)
                            if tag_id:
                                if handle_tag_addition(repo_key, tag_id):
                                    st.success(f"Created and added tag: {new_tag_name}")
                                    st.rerun()
                            else:
                                st.error(message)

def display_tag_management():
    """Display global tag management interface"""
    # [Rest of the function remains unchanged...]
