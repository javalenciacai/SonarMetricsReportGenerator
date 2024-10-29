import streamlit as st
from database.schema import (
    create_tag, get_all_tags, get_project_tags,
    add_tag_to_project, remove_tag_from_project, delete_tag
)

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
        if st.button("×", key=f"remove_tag_{tag['id']}", help="Remove tag"):
            with st.spinner("Removing tag..."):
                if remove_tag_from_project(tag['id']):
                    st.success("Tag removed successfully")
                    st.rerun()
                else:
                    st.error("Failed to remove tag")

def handle_tag_operation(operation_type, **kwargs):
    """Handle tag operations with proper state management"""
    if operation_type == "add":
        repo_key = kwargs.get('repo_key')
        tag_id = kwargs.get('tag_id')
        
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
                st.session_state.selected_tag = None
                st.session_state.tag_operation_completed = True
                return True
            else:
                st.error(f"Failed to add tag: {result.get('message', 'Unknown error')}")
                return False
    
    elif operation_type == "create":
        name = kwargs.get('name')
        color = kwargs.get('color')
        repo_key = kwargs.get('repo_key')
        
        if not name:
            st.error("Please enter a tag name")
            return False
        
        with st.spinner("Creating tag..."):
            tag_id, message = create_tag(name, color)
            if tag_id:
                result = add_tag_to_project(repo_key, tag_id)
                if result["success"]:
                    st.success(f"Created and added tag: {name}")
                    st.session_state.tag_created = True
                    return True
                else:
                    st.error(f"Created tag but failed to add: {result.get('message')}")
                    return False
            else:
                st.error(message)
                return False

def display_project_tags(repo_key):
    """Display and manage tags for a specific project"""
    st.markdown("### 🏷️ Project Tags")
    
    # Initialize session state
    if 'tag_operation_completed' not in st.session_state:
        st.session_state.tag_operation_completed = False
    if 'tag_created' not in st.session_state:
        st.session_state.tag_created = False
    if 'selected_tag' not in st.session_state:
        st.session_state.selected_tag = None
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        current_tags = get_project_tags(repo_key)
        if current_tags:
            st.markdown("Current tags:")
            for tag in current_tags:
                render_tag_badge(tag, lambda tag_id=tag['id']: remove_tag_from_project(repo_key, tag_id))
        else:
            st.info("No tags assigned to this project")
    
    with col2:
        with st.expander("➕ Add Tag", expanded=True):
            # Add existing tag
            available_tags = [tag for tag in get_all_tags() 
                            if tag['id'] not in [t['id'] for t in current_tags]]
            
            if available_tags:
                selected_tag = st.selectbox(
                    "Select tag",
                    options=available_tags,
                    format_func=lambda x: x['name'],
                    key="tag_selector",
                    index=None
                )
                
                if st.button("Add Selected Tag", 
                           disabled=not selected_tag,
                           use_container_width=True):
                    handle_tag_operation("add", repo_key=repo_key, 
                                      tag_id=selected_tag['id'] if selected_tag else None)
            else:
                st.info("No available tags to add")
            
            # Create new tag section
            st.markdown("---")
            st.markdown("##### Create New Tag")
            
            with st.form("create_tag_form", clear_on_submit=True):
                new_tag_name = st.text_input("Tag name")
                new_tag_color = st.color_picker("Tag color", value='#808080')
                submit_button = st.form_submit_button("Create Tag", 
                                                    use_container_width=True)
                
                if submit_button:
                    handle_tag_operation("create", name=new_tag_name, 
                                      color=new_tag_color, repo_key=repo_key)
    
    # Refresh UI if needed
    if st.session_state.tag_operation_completed or st.session_state.tag_created:
        st.session_state.tag_operation_completed = False
        st.session_state.tag_created = False
        st.rerun()

def display_tag_management():
    """Display global tag management interface"""
    st.markdown("### 🏷️ Tag Management")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### Existing Tags")
        tags = get_all_tags()
        if tags:
            for tag in tags:
                col_tag, col_delete = st.columns([4, 1])
                with col_tag:
                    render_tag_badge(tag)
                with col_delete:
                    if st.button("🗑️", key=f"delete_tag_{tag['id']}", 
                               help="Delete tag"):
                        with st.spinner("Deleting tag..."):
                            if delete_tag(tag['id']):
                                st.success(f"Deleted tag: {tag['name']}")
                                st.rerun()
                            else:
                                st.error("Failed to delete tag")
        else:
            st.info("No tags created yet")
    
    with col2:
        st.markdown("#### Create New Tag")
        with st.form("global_tag_form", clear_on_submit=True):
            new_tag_name = st.text_input("Tag name")
            new_tag_color = st.color_picker("Tag color", value='#808080')
            submit_button = st.form_submit_button("Create Tag", 
                                                use_container_width=True)
            
            if submit_button:
                if not new_tag_name:
                    st.error("Please enter a tag name")
                else:
                    with st.spinner("Creating tag..."):
                        tag_id, message = create_tag(new_tag_name, new_tag_color)
                        if tag_id:
                            st.success(f"Created tag: {new_tag_name}")
                            st.rerun()
                        else:
                            st.error(message)
