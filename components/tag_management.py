import streamlit as st
from database.schema import (
    create_tag, get_all_tags, get_project_tags,
    add_tag_to_project, remove_tag_from_project, delete_tag,
    edit_tag
)

def init_tag_state():
    """Initialize session state variables for tag management"""
    if 'tag_message' not in st.session_state:
        st.session_state.tag_message = {'type': None, 'content': None}
    if 'tag_operation_status' not in st.session_state:
        st.session_state.tag_operation_status = None
    if 'selected_tag_id' not in st.session_state:
        st.session_state.selected_tag_id = None
    if 'show_tag_form' not in st.session_state:
        st.session_state.show_tag_form = False
    if 'editing_tag' not in st.session_state:
        st.session_state.editing_tag = None

def show_temporary_message():
    """Display temporary success/error messages using containers"""
    if st.session_state.tag_message['type']:
        message_container = st.empty()
        if st.session_state.tag_message['type'] == 'success':
            message_container.success(st.session_state.tag_message['content'])
        elif st.session_state.tag_message['type'] == 'error':
            message_container.error(st.session_state.tag_message['content'])
        elif st.session_state.tag_message['type'] == 'warning':
            message_container.warning(st.session_state.tag_message['content'])
        # Clear message after display
        st.session_state.tag_message = {'type': None, 'content': None}

def render_tag_badge(tag, repo_key=None, on_remove=None, enable_edit=False):
    """Render a styled tag badge with optional edit functionality"""
    col1, col2 = st.columns([4, 1])
    
    with col1:
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
    
    with col2:
        if enable_edit:
            if st.button("✏️", key=f"edit_tag_{tag['id']}", help="Edit tag"):
                st.session_state.editing_tag = tag
        
        if on_remove and repo_key:
            if st.button("×", key=f"remove_tag_{tag['id']}", help="Remove tag"):
                handle_tag_operation(
                    "remove",
                    repo_key=repo_key,
                    tag_id=tag['id']
                )

def handle_tag_operation(operation_type, **kwargs):
    """Handle tag operations with improved state management and error handling"""
    st.session_state.tag_operation_status = 'processing'
    
    try:
        if operation_type == "add":
            repo_key = kwargs.get('repo_key')
            tag_id = kwargs.get('tag_id')
            
            if not tag_id:
                st.session_state.tag_message = {
                    'type': 'error',
                    'content': "Please select a tag first"
                }
                return False
            
            result = add_tag_to_project(repo_key, tag_id)
            
            if result["success"]:
                if result["status"] == "already_exists":
                    st.session_state.tag_message = {
                        'type': 'warning',
                        'content': "Tag already assigned to this project"
                    }
                else:
                    st.session_state.tag_message = {
                        'type': 'success',
                        'content': "Tag added successfully"
                    }
                st.session_state.selected_tag_id = None
                return True
            else:
                st.session_state.tag_message = {
                    'type': 'error',
                    'content': f"Failed to add tag: {result.get('message', 'Unknown error')}"
                }
                return False
                
        elif operation_type == "create":
            name = kwargs.get('name')
            color = kwargs.get('color')
            repo_key = kwargs.get('repo_key')
            
            if not name:
                st.session_state.tag_message = {
                    'type': 'error',
                    'content': "Please enter a tag name"
                }
                return False
            
            tag_id, message = create_tag(name, color)
            if tag_id:
                if repo_key:
                    result = add_tag_to_project(repo_key, tag_id)
                    if result["success"]:
                        st.session_state.tag_message = {
                            'type': 'success',
                            'content': f"Created and added tag: {name}"
                        }
                        st.session_state.show_tag_form = False
                        return True
                    else:
                        st.session_state.tag_message = {
                            'type': 'error',
                            'content': f"Created tag but failed to add: {result.get('message')}"
                        }
                        return False
                else:
                    st.session_state.tag_message = {
                        'type': 'success',
                        'content': f"Created tag: {name}"
                    }
                    return True
            else:
                st.session_state.tag_message = {
                    'type': 'error',
                    'content': message
                }
                return False
                
        elif operation_type == "edit":
            tag_id = kwargs.get('tag_id')
            name = kwargs.get('name')
            color = kwargs.get('color')
            
            success, message = edit_tag(tag_id, name, color)
            if success:
                st.session_state.tag_message = {
                    'type': 'success',
                    'content': message
                }
                st.session_state.editing_tag = None
                return True
            else:
                st.session_state.tag_message = {
                    'type': 'error',
                    'content': message
                }
                return False
                
        elif operation_type == "remove":
            repo_key = kwargs.get('repo_key')
            tag_id = kwargs.get('tag_id')
            
            if remove_tag_from_project(repo_key, tag_id):
                st.session_state.tag_message = {
                    'type': 'success',
                    'content': "Tag removed successfully"
                }
                return True
            else:
                st.session_state.tag_message = {
                    'type': 'error',
                    'content': "Failed to remove tag"
                }
                return False
                
    finally:
        st.session_state.tag_operation_status = None

def display_project_tags(repo_key):
    """Display and manage tags for a specific project with optimized UI updates"""
    st.markdown("### 🏷️ Project Tags")
    init_tag_state()
    show_temporary_message()
    
    # Create containers for dynamic updates
    tags_container = st.empty()
    operation_container = st.empty()
    
    with tags_container.container():
        current_tags = get_project_tags(repo_key)
        if current_tags:
            st.markdown("Current tags:")
            for tag in current_tags:
                render_tag_badge(tag, repo_key=repo_key, on_remove=True)
        else:
            st.info("No tags assigned to this project")
    
    with operation_container.container():
        col1, col2 = st.columns([3, 1])
        
        with col2:
            with st.expander("➕ Add Tag", expanded=True):
                available_tags = [tag for tag in get_all_tags() 
                                if tag['id'] not in [t['id'] for t in current_tags]]
                
                if available_tags:
                    st.selectbox(
                        "Select tag",
                        options=available_tags,
                        format_func=lambda x: x['name'],
                        key='tag_selector',
                        index=None,
                        on_change=lambda: setattr(
                            st.session_state, 
                            'selected_tag_id',
                            st.session_state.tag_selector['id'] if st.session_state.tag_selector else None
                        )
                    )
                    
                    st.button(
                        "Add Selected Tag",
                        disabled=not st.session_state.selected_tag_id,
                        use_container_width=True,
                        on_click=lambda: handle_tag_operation(
                            "add",
                            repo_key=repo_key,
                            tag_id=st.session_state.selected_tag_id
                        )
                    )
                else:
                    st.info("No available tags to add")
                
                st.markdown("---")
                st.markdown("##### Create New Tag")
                
                with st.form("create_tag_form", clear_on_submit=True):
                    new_tag_name = st.text_input("Tag name")
                    new_tag_color = st.color_picker("Tag color", value='#808080')
                    
                    submit_button = st.form_submit_button(
                        "Create Tag",
                        use_container_width=True,
                        on_click=lambda: handle_tag_operation(
                            "create",
                            name=new_tag_name,
                            color=new_tag_color,
                            repo_key=repo_key
                        )
                    )

def display_tag_management():
    """Display global tag management interface with optimized updates"""
    st.markdown("### 🏷️ Tag Management")
    init_tag_state()
    show_temporary_message()
    
    tags_container = st.empty()
    form_container = st.empty()
    
    with tags_container.container():
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("#### Existing Tags")
            tags = get_all_tags()
            if tags:
                for tag in tags:
                    col_tag, col_buttons = st.columns([4, 1])
                    with col_tag:
                        render_tag_badge(tag, enable_edit=True)
                    with col_buttons:
                        if st.button(
                            "🗑️",
                            key=f"delete_tag_{tag['id']}",
                            help="Delete tag"
                        ):
                            if delete_tag(tag['id']):
                                st.session_state.tag_message = {
                                    'type': 'success',
                                    'content': "Tag deleted successfully"
                                }
                                st.experimental_rerun()
                            else:
                                st.session_state.tag_message = {
                                    'type': 'error',
                                    'content': "Failed to delete tag"
                                }
            else:
                st.info("No tags created yet")
        
        with col2:
            if st.session_state.editing_tag:
                st.markdown("#### Edit Tag")
                with st.form("edit_tag_form"):
                    edit_name = st.text_input("Tag name", value=st.session_state.editing_tag['name'])
                    edit_color = st.color_picker("Tag color", value=st.session_state.editing_tag['color'])
                    
                    col_submit, col_cancel = st.columns(2)
                    with col_submit:
                        if st.form_submit_button("Save Changes"):
                            handle_tag_operation(
                                "edit",
                                tag_id=st.session_state.editing_tag['id'],
                                name=edit_name,
                                color=edit_color
                            )
                    with col_cancel:
                        if st.form_submit_button("Cancel"):
                            st.session_state.editing_tag = None
            else:
                st.markdown("#### Create New Tag")
                with st.form("global_tag_form", clear_on_submit=True):
                    new_tag_name = st.text_input("Tag name")
                    new_tag_color = st.color_picker("Tag color", value='#808080')
                    
                    if st.form_submit_button(
                        "Create Tag",
                        use_container_width=True
                    ):
                        handle_tag_operation(
                            "create",
                            name=new_tag_name,
                            color=new_tag_color
                        )
                        st.experimental_rerun()

def delete_tag_handler(tag_id):
    """Handle tag deletion with proper state management"""
    if delete_tag(tag_id):
        st.session_state.tag_message = {
            'type': 'success',
            'content': "Tag deleted successfully"
        }
        st.experimental_rerun()
    else:
        st.session_state.tag_message = {
            'type': 'error',
            'content': "Failed to delete tag"
        }
