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
        st.button("×", key=f"remove_tag_{tag['id']}", on_click=on_remove, args=(tag['id'],))

def display_project_tags(repo_key):
    """Display and manage tags for a specific project"""
    st.markdown("### 🏷️ Project Tags")
    
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
        with st.expander("➕ Add Tag"):
            # Add existing tag
            available_tags = [tag for tag in all_tags if tag['id'] not in [t['id'] for t in current_tags]]
            if available_tags:
                selected_tag = st.selectbox(
                    "Select tag",
                    options=available_tags,
                    format_func=lambda x: x['name']
                )
                if st.button("Add Selected Tag"):
                    if add_tag_to_project(repo_key, selected_tag['id']):
                        st.success(f"Added tag: {selected_tag['name']}")
                        st.rerun()
            
            # Create new tag
            st.markdown("---")
            st.markdown("##### Create New Tag")
            new_tag_name = st.text_input("Tag name", key="new_tag_name")
            new_tag_color = st.color_picker("Tag color", value='#808080', key="new_tag_color")
            
            if st.button("Create Tag"):
                if new_tag_name:
                    tag_id = create_tag(new_tag_name, new_tag_color)
                    if tag_id and add_tag_to_project(repo_key, tag_id):
                        st.success(f"Created and added tag: {new_tag_name}")
                        st.rerun()
                else:
                    st.warning("Please enter a tag name")

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
                    if st.button("🗑️", key=f"delete_tag_{tag['id']}"):
                        if delete_tag(tag['id']):
                            st.success(f"Deleted tag: {tag['name']}")
                            st.rerun()
        else:
            st.info("No tags created yet")
    
    with col2:
        st.markdown("#### Create New Tag")
        new_tag_name = st.text_input("Tag name")
        new_tag_color = st.color_picker("Tag color", value='#808080')
        
        if st.button("Create Tag"):
            if new_tag_name:
                if create_tag(new_tag_name, new_tag_color):
                    st.success(f"Created tag: {new_tag_name}")
                    st.rerun()
            else:
                st.warning("Please enter a tag name")
