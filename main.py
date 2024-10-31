[Previous code until line 326 remains the same...]

            if selected_project == 'all':
                st.markdown("## 📊 All Projects Overview")
                
                # Combined projects data dictionary for both active and inactive projects
                projects_data = {}
                
                # Process all projects
                for project_key, status in project_status.items():
                    if project_key == 'all':
                        continue
                        
                    project_data = {
                        'name': status['name'],
                        'is_active': status['is_active'],
                        'is_marked_for_deletion': status.get('is_marked_for_deletion', False),
                        'metrics': None
                    }
                    
                    # Try to get current metrics for active projects
                    if status['is_active']:
                        try:
                            metrics = sonar_api.get_project_metrics(project_key)
                            if metrics:
                                project_data['metrics'] = {m['metric']: float(m['value']) for m in metrics}
                            else:
                                # Mark project as inactive if no metrics found
                                metrics_processor.mark_project_inactive(project_key)
                                logger.warning(f"Project {project_key} marked as inactive - no metrics found")
                        except requests.exceptions.HTTPError as e:
                            if e.response.status_code == 404:
                                # Mark project as inactive on 404
                                metrics_processor.mark_project_inactive(project_key)
                                logger.warning(f"Project {project_key} marked as inactive - not found in SonarCloud")
                    
                    # If project is inactive or no current metrics, get historical data
                    if not project_data['metrics']:
                        latest_metrics = metrics_processor.get_latest_metrics(project_key)
                        if latest_metrics:
                            project_data['metrics'] = {
                                'bugs': float(latest_metrics.get('bugs', 0)),
                                'vulnerabilities': float(latest_metrics.get('vulnerabilities', 0)),
                                'code_smells': float(latest_metrics.get('code_smells', 0)),
                                'coverage': float(latest_metrics.get('coverage', 0)),
                                'duplicated_lines_density': float(latest_metrics.get('duplicated_lines_density', 0)),
                                'ncloc': float(latest_metrics.get('ncloc', 0)),
                                'sqale_index': float(latest_metrics.get('sqale_index', 0)),
                                'timestamp': latest_metrics.get('timestamp'),
                                'last_seen': latest_metrics.get('last_seen'),
                                'inactive_duration': latest_metrics.get('inactive_duration')
                            }
                    
                    # Add project to data dictionary if we have metrics
                    if project_data['metrics']:
                        projects_data[project_key] = project_data
                
                # Display all projects or filter based on inactive setting
                filtered_projects_data = {}
                for project_key, data in projects_data.items():
                    if show_inactive or data['is_active']:
                        filtered_projects_data[project_key] = data
                
                if filtered_projects_data:
                    display_multi_project_metrics(filtered_projects_data)
                    plot_multi_project_comparison(filtered_projects_data)
                    create_download_report(filtered_projects_data)
                else:
                    st.info("No projects found matching the current filter settings")
            
[Rest of the file remains the same...]
