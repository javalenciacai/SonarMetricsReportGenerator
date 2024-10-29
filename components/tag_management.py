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
    if 'tag_create_submitted' not in st.session_state:
        st.session_state.tag_create_submitted = False
    if 'tag_removal_status' not in st.session_state:
        st.session_state.tag_removal_status = {}

def show_temporary_message(message_container=None):
    """Display temporary success/error messages using containers"""
    if message_container is None:
        message_container = st.empty()
        
    if st.session_state.tag_message['type']:
        if st.session_state.tag_message['type'] == 'success':
            message_container.success(st.session_state.tag_message['content'])
        elif st.session_state.tag_message['type'] == 'error':
            message_container.error(st.session_state.tag_message['content'])
        elif st.session_state.tag_message['type'] == 'warning':
            message_container.warning(st.session_state.tag_message['content'])
        # Clear message after display
        st.session_state.tag_message = {'type': None, 'content': None}

def render_tag_badge(tag, repo_key=None, on_remove=None, enable_edit=False):
    """Render a styled tag badge with enhanced edit functionality"""
    tag_col, edit_col, remove_col = st.columns([6, 1, 1])
    
    with tag_col:
        html = f"""
            <div style="
                display: inline-flex;
                align-items: center;
                background-color: {tag['color']};
                color: {'#000' if tag['color'] in ['#FFFFFF', '#FFE4E1', '#E0FFFF', '#F0F8FF'] else '#FFF'};
                padding: 4px 12px;
                border-radius: 15px;
                margin: 2px;
                font-size: 0.9rem;">
                {tag['name']}
                <span style="font-size: 0.75rem; margin-left: 8px; opacity: 0.8;">
                    {tag['updated_at'].strftime('%Y-%m-%d %H:%M') if tag.get('updated_at') else ''}
                </span>
            </div>
        """
        st.markdown(html, unsafe_allow_html=True)
    
    with edit_col:
        if enable_edit:
            if st.button("✏️", key=f"edit_tag_{tag['id']}", 
                        help="Edit tag", use_container_width=True):
                st.session_state.editing_tag = tag
                st.session_state.show_tag_form = False
    
    with remove_col:
        if on_remove and repo_key:
            removal_status = st.session_state.tag_removal_status.get(f"{repo_key}_{tag['id']}", None)
            if removal_status == 'processing':
                st.markdown("⏳")
            else:
                if st.button("🗑️", key=f"remove_tag_{tag['id']}", 
                            help="Remove tag", use_container_width=True):
                    st.session_state.tag_removal_status[f"{repo_key}_{tag['id']}"] = 'processing'
                    handle_tag_operation(
                        "remove",
                        repo_key=repo_key,
                        tag_id=tag['id']
                    )

def handle_tag_operation(operation_type, **kwargs):
    """Handle tag operations with improved state management and visual feedback"""
    if st.session_state.tag_operation_status == 'processing':
        return False

    st.session_state.tag_operation_status = 'processing'
    loading_container = st.empty()
    loading_container.info("⏳ Processing operation...")
    
    try:
        if operation_type == "create":
            name = kwargs.get('name')
            color = kwargs.get('color')
            
            if not name:
                st.session_state.tag_message = {
                    'type': 'error',
                    'content': "❌ Tag name is required"
                }
                return False
            
            tag_id, message = create_tag(name, color)
            if tag_id:
                st.session_state.tag_message = {
                    'type': 'success',
                    'content': "✅ Tag created successfully"
                }
                return True
            else:
                st.session_state.tag_message = {
                    'type': 'error',
                    'content': "❌ " + message
                }
                return False
                
        elif operation_type == "remove":
            repo_key = kwargs.get('repo_key')
            tag_id = kwargs.get('tag_id')
            
            if remove_tag_from_project(repo_key, tag_id):
                st.session_state.tag_message = {
                    'type': 'success',
                    'content': "🗑️ Tag removed successfully"
                }
                # Clear removal status
                status_key = f"{repo_key}_{tag_id}"
                if status_key in st.session_state.tag_removal_status:
                    del st.session_state.tag_removal_status[status_key]
                return True
            else:
                st.session_state.tag_message = {
                    'type': 'error',
                    'content': "❌ Failed to remove tag"
                }
                return False
                
        elif operation_type == "edit":
            tag_id = kwargs.get('tag_id')
            name = kwargs.get('name')
            color = kwargs.get('color')
            
            if not name:
                st.session_state.tag_message = {
                    'type': 'error',
                    'content': "❌ Tag name is required"
                }
                return False
            
            success, message = edit_tag(tag_id, name, color)
            if success:
                st.session_state.tag_message = {
                    'type': 'success',
                    'content': "✅ " + message
                }
                st.session_state.editing_tag = None
                return True
            else:
                st.session_state.tag_message = {
                    'type': 'error',
                    'content': "❌ " + message
                }
                return False
                
    finally:
        st.session_state.tag_operation_status = None
        loading_container.empty()

def display_edit_form(tag, on_save=None):
    """Display the edit form in a more prominent location"""
    st.markdown("### ✏️ Edit Tag")
    
    with st.form(key=f"edit_tag_form_{tag['id']}", clear_on_submit=False):
        edit_name = st.text_input("Tag name", value=tag['name'])
        edit_color = st.color_picker("Tag color", value=tag['color'])
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 Save Changes", use_container_width=True):
                if handle_tag_operation(
                    "edit",
                    tag_id=tag['id'],
                    name=edit_name,
                    color=edit_color
                ):
                    if on_save:
                        on_save()
                    return True
        with col2:
            if st.form_submit_button("❌ Cancel", use_container_width=True):
                st.session_state.editing_tag = None
                return False

def display_project_tags(repo_key):
    """Display and manage tags for a specific project with optimized UI updates"""
    st.markdown("### 🏷️ Project Tags")
    init_tag_state()
    
    # Create containers for dynamic updates
    message_container = st.empty()
    show_temporary_message(message_container)
    
    tags_container = st.container()
    edit_container = st.container()
    operation_container = st.container()
    
    with tags_container:
        current_tags = get_project_tags(repo_key)
        if current_tags:
            st.markdown("Current tags:")
            for tag in current_tags:
                render_tag_badge(tag, repo_key=repo_key, on_remove=True)
        else:
            st.info("No tags assigned to this project")
    
    if st.session_state.editing_tag:
        with edit_container:
            display_edit_form(
                st.session_state.editing_tag,
                on_save=lambda: st.experimental_rerun()
            )
    
    with operation_container:
        col1, col2 = st.columns([3, 1])
        
        with col2:
            with st.expander("➕ Add/Create Tag", expanded=True):
                available_tags = [tag for tag in get_all_tags() 
                                if tag['id'] not in [t['id'] for t in current_tags]]
                
                if available_tags:
                    st.markdown("##### Add Existing Tag")
                    selected_tag = st.selectbox(
                        "Select tag",
                        options=available_tags,
                        format_func=lambda x: x['name'],
                        key='tag_selector',
                        index=None
                    )
                    
                    if selected_tag:
                        st.session_state.selected_tag_id = selected_tag['id']
                    
                    add_button = st.button(
                        "Add Selected Tag",
                        disabled=not st.session_state.selected_tag_id or st.session_state.tag_operation_status == 'processing',
                        use_container_width=True
                    )
                    
                    if add_button:
                        if handle_tag_operation(
                            "add",
                            repo_key=repo_key,
                            tag_id=st.session_state.selected_tag_id
                        ):
                            st.experimental_rerun()
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
                        disabled=st.session_state.tag_operation_status == 'processing'
                    )
                    
                    if submit_button and not st.session_state.tag_create_submitted:
                        st.session_state.tag_create_submitted = True
                        if handle_tag_operation(
                            "create",
                            name=new_tag_name,
                            color=new_tag_color,
                            repo_key=repo_key
                        ):
                            st.experimental_rerun()

def display_tag_management():
    """Display global tag management interface with optimized UI updates"""
    st.markdown("### 🏷️ Tag Management")
    init_tag_state()
    
    message_container = st.empty()
    show_temporary_message(message_container)
    
    main_container = st.container()
    edit_container = st.empty()
    create_container = st.container()
    
    with main_container:
        st.markdown("#### Existing Tags")
        tags = get_all_tags()
        if tags:
            for tag in tags:
                render_tag_badge(tag, enable_edit=True)
        else:
            st.info("No tags created yet")
    
    if st.session_state.editing_tag:
        with edit_container:
            display_edit_form(
                st.session_state.editing_tag,
                on_save=lambda: st.experimental_rerun()
            )
    
    with create_container:
        if not st.session_state.editing_tag:
            st.markdown("### ➕ Create New Tag")
            with st.form("create_tag_form", clear_on_submit=True):
                new_tag_name = st.text_input("Tag name")
                new_tag_color = st.color_picker("Tag color", value='#808080')
                
                submit_button = st.form_submit_button(
                    "Create Tag",
                    use_container_width=True,
                    disabled=st.session_state.tag_operation_status == 'processing'
                )
                
                if submit_button and not st.session_state.tag_create_submitted:
                    st.session_state.tag_create_submitted = True
                    if handle_tag_operation(
                        "create",
                        name=new_tag_name,
                        color=new_tag_color
                    ):
                        st.experimental_rerun()
                elif not submit_button:
                    st.session_state.tag_create_submitted = False
