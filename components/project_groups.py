import streamlit as st
from database.schema import (
    create_project_group,
    delete_project_group,
    add_project_to_group,
    remove_project_from_group,
    get_project_groups
)
from datetime import datetime, timedelta

def manage_project_groups(active_projects, project_names):
    """Display and manage project groups"""
    st.markdown("## 📁 Project Groups")
    
    # Initialize session state for group management
    if 'group_cache' not in st.session_state:
        st.session_state.group_cache = {'data': None, 'last_updated': None}
    if 'new_group_created' not in st.session_state:
        st.session_state.new_group_created = False
    if 'group_action_performed' not in st.session_state:
        st.session_state.group_action_performed = False
        
    # Cache invalidation check (5 minutes)
    cache_valid = (
        st.session_state.group_cache['last_updated'] is not None and
        datetime.now() - st.session_state.group_cache['last_updated'] < timedelta(minutes=5)
    )
    
    # Get groups data with caching
    if not cache_valid or st.session_state.group_action_performed:
        groups = get_project_groups()
        st.session_state.group_cache = {
            'data': groups,
            'last_updated': datetime.now()
        }
        st.session_state.group_action_performed = False
    else:
        groups = st.session_state.group_cache['data']
    
    # Create new group section
    st.markdown("### Create New Group")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        new_group_name = st.text_input("Group Name", key="new_group_name")
        new_group_desc = st.text_area("Description", key="new_group_desc", height=100)
    
    with col2:
        if st.button("➕ Create Group", disabled=not new_group_name):
            if not new_group_name.strip():
                st.error("Group name cannot be empty")
            else:
                group_id = create_project_group(new_group_name, new_group_desc)
                if group_id:
                    st.session_state.group_action_performed = True
                    st.success(f"Group '{new_group_name}' created successfully!")
                    st.session_state.new_group_name = ""
                    st.session_state.new_group_desc = ""
                else:
                    st.error("Failed to create group")
    
    # Display refresh button
    if st.button("🔄 Refresh Groups"):
        st.session_state.group_action_performed = True
        st.experimental_rerun()
    
    # Display existing groups
    if groups:
        st.markdown("### Existing Groups")
        for group in groups:
            with st.expander(f"📁 {group['name']} ({group['project_count']} projects)", expanded=False):
                # Group description
                if group['description']:
                    st.markdown(f"*{group['description']}*")
                
                # Current members
                st.markdown("#### Current Members")
                if group['projects'] and group['projects'][0] is not None:
                    for repo_key, project_name in zip(group['projects'], group['project_names']):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"- {project_name}")
                        with col2:
                            remove_key = f"remove_{group['id']}_{repo_key}"
                            if st.button("🗑️", key=remove_key):
                                if remove_project_from_group(group['id'], repo_key):
                                    st.session_state.group_action_performed = True
                                    st.success(f"Removed {project_name} from group")
                                    st.experimental_rerun()
                                else:
                                    st.error("Failed to remove project from group")
                else:
                    st.info("No projects in this group")
                
                # Add new members
                st.markdown("#### Add Projects")
                available_projects = {
                    key: name for key, name in project_names.items()
                    if key != 'all' and (not group['projects'] or key not in group['projects'])
                }
                
                if available_projects:
                    selected_project = st.selectbox(
                        "Select Project",
                        options=list(available_projects.keys()),
                        format_func=lambda x: available_projects[x],
                        key=f"add_project_{group['id']}"
                    )
                    
                    add_key = f"add_btn_{group['id']}"
                    if st.button("➕ Add to Group", key=add_key):
                        if add_project_to_group(group['id'], selected_project):
                            st.session_state.group_action_performed = True
                            st.success(f"Added {available_projects[selected_project]} to group")
                            st.experimental_rerun()
                        else:
                            st.error("Failed to add project to group")
                else:
                    st.info("No available projects to add")
                
                # Group actions
                st.markdown("#### Group Actions")
                delete_key = f"delete_group_{group['id']}"
                if st.button("🗑️ Delete Group", key=delete_key):
                    if delete_project_group(group['id']):
                        st.session_state.group_action_performed = True
                        st.success(f"Group '{group['name']}' deleted successfully")
                        st.experimental_rerun()
                    else:
                        st.error("Failed to delete group")
    else:
        st.info("No project groups created yet")

def get_group_metrics(sonar_api, group_projects):
    """Get metrics for all projects in a group with caching"""
    cache_key = f"group_metrics_{','.join(sorted(group_projects))}"
    
    if cache_key not in st.session_state or st.session_state.get('refresh_metrics', False):
        group_metrics = {}
        for project_key in group_projects:
            metrics = sonar_api.get_project_metrics(project_key)
            if metrics:
                metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                group_metrics[project_key] = metrics_dict
        
        st.session_state[cache_key] = {
            'data': group_metrics,
            'timestamp': datetime.now()
        }
        st.session_state.refresh_metrics = False
    
    return st.session_state[cache_key]['data']
