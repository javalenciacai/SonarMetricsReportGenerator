import streamlit as st
from database.schema import (
    create_project_group,
    get_project_groups,
    get_projects_in_group,
    assign_project_to_group,
    remove_project_from_group,
    delete_project_group
)
from services.metrics_processor import MetricsProcessor
from components.metrics_display import display_multi_project_metrics
from components.visualizations import plot_multi_project_comparison

def check_existing_group(name):
    """Check if a group with the given name already exists"""
    existing_groups = get_project_groups()
    return any(group['name'].lower() == name.lower() for group in existing_groups)

def validate_group_input(name, description):
    """Validate group creation input"""
    if not name:
        return False, "Group name is required"
    if len(name) < 3:
        return False, "Group name must be at least 3 characters long"
    if len(name) > 50:
        return False, "Group name must be less than 50 characters"
    if check_existing_group(name):
        return False, "A group with this name already exists"
    if description and len(description) > 500:
        return False, "Description must be less than 500 characters"
    return True, ""

def manage_project_groups(sonar_api):
    """Manage project groups and display grouped metrics"""
    st.markdown("## 👥 Project Groups")
    
    tab1, tab2 = st.tabs(["📊 Group View", "⚙️ Group Management"])
    
    with tab1:
        display_grouped_metrics(sonar_api)
    
    with tab2:
        manage_groups(sonar_api)

def manage_groups(sonar_api):
    """Interface for creating and managing project groups"""
    # Initialize session state for form and confirmations
    if 'group_form_submitted' not in st.session_state:
        st.session_state.group_form_submitted = False
        st.session_state.group_name = ""
        st.session_state.group_description = ""
        st.session_state.show_delete_confirm = {}
        st.session_state.show_remove_confirm = {}

    st.markdown("### Create New Group")
    
    # Create New Group Form with validation
    with st.form(key="create_group_form"):
        group_name = st.text_input(
            "Group Name",
            value=st.session_state.group_name,
            help="Enter a unique name for the group (3-50 characters)"
        )
        group_description = st.text_area(
            "Group Description",
            value=st.session_state.group_description,
            height=100,
            help="Optional: Describe the purpose of this group (max 500 characters)"
        )
        create_group = st.form_submit_button("➕ Create Group")
        
        if create_group:
            # Validate input
            is_valid, error_message = validate_group_input(group_name, group_description)
            
            if is_valid:
                group_id = create_project_group(group_name, group_description)
                if group_id:
                    st.success(f"✅ Group '{group_name}' created successfully!")
                    # Clear form inputs
                    st.session_state.group_name = ""
                    st.session_state.group_description = ""
                    st.session_state.group_form_submitted = True
                    st.rerun()
                else:
                    st.error("Failed to create group. Please try again.")
            else:
                st.error(error_message)
    
    # Display existing groups with management options
    st.markdown("### Existing Groups")
    groups = get_project_groups()
    
    if not groups:
        st.info("No groups created yet.")
        return
    
    metrics_processor = MetricsProcessor()
    projects = sonar_api.get_projects()
    
    for group in groups:
        with st.expander(f"📁 {group['name']}", expanded=True):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                if group['description']:
                    st.markdown(f"*{group['description']}*")
                
                # Get and display project count and list
                group_projects = metrics_processor.get_projects_in_group(group['id'])
                project_count = len(group_projects) if group_projects else 0
                st.markdown(f"**Projects in group:** {project_count}")
                
                # Project assignment interface
                if projects:
                    st.markdown("#### Manage Projects")
                    
                    # Create sets of project keys for easier comparison
                    group_project_keys = {p['repo_key'] for p in group_projects} if group_projects else set()
                    available_projects = [p for p in projects if p['key'] not in group_project_keys]
                    
                    # Add projects to group
                    if available_projects:
                        selected_projects = st.multiselect(
                            "Add Projects to Group",
                            options=[p['key'] for p in available_projects],
                            format_func=lambda x: next(p['name'] for p in available_projects if p['key'] == x),
                            key=f"add_projects_{group['id']}"
                        )
                        
                        if selected_projects:
                            col3, col4 = st.columns([3, 1])
                            with col4:
                                if st.button("➕ Add Selected", key=f"add_btn_{group['id']}"):
                                    success_count = 0
                                    for project_key in selected_projects:
                                        if assign_project_to_group(project_key, group['id']):
                                            success_count += 1
                                    if success_count > 0:
                                        st.success(f"Added {success_count} projects to the group")
                                        st.rerun()
                                    else:
                                        st.error("Failed to add projects")
                    
                    # List and manage current projects
                    if group_projects:
                        st.markdown("#### Current Projects")
                        for project in group_projects:
                            col5, col6 = st.columns([3, 1])
                            with col5:
                                st.markdown(f"• {project['name']}")
                            with col6:
                                # Initialize remove confirmation state
                                if f"remove_{project['repo_key']}" not in st.session_state.show_remove_confirm:
                                    st.session_state.show_remove_confirm[f"remove_{project['repo_key']}"] = False
                                
                                if not st.session_state.show_remove_confirm[f"remove_{project['repo_key']}"]:
                                    if st.button("🗑️", key=f"remove_btn_{project['repo_key']}"):
                                        st.session_state.show_remove_confirm[f"remove_{project['repo_key']}"] = True
                                else:
                                    if st.button("✅ Confirm Remove", key=f"confirm_remove_{project['repo_key']}"):
                                        if remove_project_from_group(project['repo_key']):
                                            st.success(f"Removed {project['name']} from group")
                                            st.session_state.show_remove_confirm[f"remove_{project['repo_key']}"] = False
                                            st.rerun()
                                        else:
                                            st.error("Failed to remove project")
                                    if st.button("❌ Cancel", key=f"cancel_remove_{project['repo_key']}"):
                                        st.session_state.show_remove_confirm[f"remove_{project['repo_key']}"] = False
                                        st.rerun()
            
            with col2:
                # Initialize confirmation state for this group if not exists
                if str(group['id']) not in st.session_state.show_delete_confirm:
                    st.session_state.show_delete_confirm[str(group['id'])] = False
                
                if not st.session_state.show_delete_confirm[str(group['id'])]:
                    if st.button("🗑️ Delete Group", key=f"delete_{group['id']}"):
                        st.session_state.show_delete_confirm[str(group['id'])] = True
                else:
                    st.warning("Are you sure you want to delete this group?")
                    col7, col8 = st.columns(2)
                    with col7:
                        if st.button("✅ Yes", key=f"confirm_{group['id']}"):
                            success, message = delete_project_group(group['id'])
                            if success:
                                st.success("Group deleted successfully!")
                                st.session_state.show_delete_confirm[str(group['id'])] = False
                                st.rerun()
                            else:
                                st.error(f"Failed to delete group: {message}")
                    with col8:
                        if st.button("❌ No", key=f"cancel_{group['id']}"):
                            st.session_state.show_delete_confirm[str(group['id'])] = False
                            st.rerun()
            
            st.markdown("---")

def display_grouped_metrics(sonar_api):
    """Display metrics grouped by project groups"""
    groups = get_project_groups()
    if not groups:
        st.info("No project groups created yet. Use the Group Management tab to create groups.")
        return
    
    metrics_processor = MetricsProcessor()
    
    for group in groups:
        with st.expander(f"📊 {group['name']}", expanded=True):
            if group['description']:
                st.markdown(f"*{group['description']}*")
            
            # Get projects in this group
            projects_data = {}
            group_projects = metrics_processor.get_projects_in_group(group['id'])
            
            if not group_projects:
                st.info("No projects in this group yet")
                continue
            
            for project in group_projects:
                try:
                    metrics = sonar_api.get_project_metrics(project['repo_key'])
                    if metrics:
                        metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                        projects_data[project['repo_key']] = {
                            'name': project['name'],
                            'metrics': metrics_dict
                        }
                except Exception as e:
                    st.warning(f"Could not fetch metrics for {project['name']}: {str(e)}")
            
            if projects_data:
                display_multi_project_metrics(projects_data)
                plot_multi_project_comparison(projects_data)
            else:
                st.warning("No metric data available for projects in this group")
