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
    # Create New Group Form
    st.markdown("### Create New Group")
    with st.form(key="create_group_form"):
        group_name = st.text_input("Group Name")
        group_description = st.text_area("Group Description", height=100)
        create_group = st.form_submit_button("➕ Create Group")
        
        if create_group and group_name:
            group_id = create_project_group(group_name, group_description)
            if group_id:
                st.success(f"✅ Group '{group_name}' created successfully!")
                st.experimental_rerun()
            else:
                st.error("Failed to create group")
    
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
                st.experimental_rerun()

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
