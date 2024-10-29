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
    st.markdown("### Create New Group")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        group_name = st.text_input("Group Name")
    with col2:
        create_group = st.button("➕ Create Group")
    
    group_description = st.text_area("Group Description", height=100)
    
    if create_group and group_name:
        group_id = create_project_group(group_name, group_description)
        if group_id:
            st.success(f"✅ Group '{group_name}' created successfully!")
            st.rerun()
        else:
            st.error("Failed to create group")
    
    st.markdown("### Assign Projects to Groups")
    
    # Get all projects
    projects = sonar_api.get_projects()
    if not projects:
        st.warning("No projects found")
        return
    
    # Get all groups
    groups = get_project_groups()
    if not groups:
        st.warning("No groups created yet")
        return
    
    # Create a mapping of group IDs to names
    group_names = {str(group['id']): group['name'] for group in groups}
    group_names[''] = 'No Group'
    
    # Create a selection widget for each project
    st.markdown("#### Project Assignments")
    
    for project in projects:
        col1, col2 = st.columns([3, 1])
        with col1:
            current_group = str(project.get('group_id', ''))
            new_group = st.selectbox(
                f"📁 {project['name']}",
                options=[''] + [str(g['id']) for g in groups],
                format_func=lambda x: group_names[x],
                key=f"group_select_{project['key']}"
            )
        
        with col2:
            if new_group != current_group:
                if st.button("Save", key=f"save_{project['key']}"):
                    if new_group:
                        if assign_project_to_group(project['key'], int(new_group)):
                            st.success("✅ Project assigned to group")
                            st.rerun()
                        else:
                            st.error("Failed to assign project to group")
                    else:
                        if remove_project_from_group(project['key']):
                            st.success("✅ Project removed from group")
                            st.rerun()
                        else:
                            st.error("Failed to remove project from group")

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
