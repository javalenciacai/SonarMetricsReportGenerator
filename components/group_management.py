import streamlit as st
from database.schema import (
    create_project_group,
    get_project_groups,
    assign_project_to_group,
    remove_project_from_group
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
    # Initialize session state for form
    if 'group_form_submitted' not in st.session_state:
        st.session_state.group_form_submitted = False
        st.session_state.group_name = ""
        st.session_state.group_description = ""

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
    
    st.markdown("### Assign Projects to Groups")
    
    # Get all projects and groups
    projects = sonar_api.get_projects()
    groups = get_project_groups()
    
    if not projects:
        st.warning("No projects found")
        return
    
    if not groups:
        st.warning("No groups created yet")
        return
    
    # Create a mapping of group IDs to names
    group_names = {str(group['id']): group['name'] for group in groups}
    group_names[''] = 'No Group'
    
    # Batch project assignments in a single form
    with st.form(key="project_assignments_form"):
        st.markdown("#### Project Assignments")
        assignments = {}
        
        for project in projects:
            current_group = str(project.get('group_id', ''))
            new_group = st.selectbox(
                f"📁 {project['name']}",
                options=[''] + [str(g['id']) for g in groups],
                format_func=lambda x: group_names[x],
                key=f"group_select_{project['key']}",
                index=[''] + [str(g['id']) for g in groups].index(current_group) if current_group else 0
            )
            if new_group != current_group:
                assignments[project['key']] = new_group
        
        save_assignments = st.form_submit_button("Save All Changes")
        
        if save_assignments and assignments:
            success = True
            for project_key, group_id in assignments.items():
                if group_id:
                    if not assign_project_to_group(project_key, int(group_id)):
                        success = False
                        st.error(f"Failed to assign project {project_key} to group")
                else:
                    if not remove_project_from_group(project_key):
                        success = False
                        st.error(f"Failed to remove project {project_key} from group")
            
            if success:
                st.success("✅ Project assignments updated successfully")
                st.rerun()

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
                metrics = sonar_api.get_project_metrics(project['repo_key'])
                if metrics:
                    metrics_dict = {m['metric']: float(m['value']) for m in metrics}
                    projects_data[project['repo_key']] = {
                        'name': project['name'],
                        'metrics': metrics_dict
                    }
            
            if projects_data:
                display_multi_project_metrics(projects_data)
                plot_multi_project_comparison(projects_data)
            else:
                st.warning("No metric data available for projects in this group")
