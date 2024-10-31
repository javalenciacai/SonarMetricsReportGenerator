[Previous code until line 150 remains the same...]

        .status-active {
            background: #2F855A;
            color: #FAFAFA;
        }
        .status-inactive {
            background: #C53030;
            color: #FAFAFA;
        }
        .data-freshness {
            font-size: 0.8rem;
            color: #A0AEC0;
            margin-top: 0.25rem;
            font-style: italic;
        }
        .metric-card-inactive {
            opacity: 0.8;
            position: relative;
        }
        .metric-card-inactive::after {
            content: "Historical Data";
            position: absolute;
            top: 0.5rem;
            right: 0.5rem;
            font-size: 0.7rem;
            color: #A0AEC0;
            background: #2D3748;
            padding: 0.2rem 0.5rem;
            border-radius: 0.25rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    analyzer = MetricAnalyzer()
    
    # Calculate total metrics including all projects
    total_metrics = {
        'ncloc': 0,
        'bugs': 0,
        'vulnerabilities': 0,
        'code_smells': 0,
        'sqale_index': 0,
        'active_count': 0,
        'inactive_count': 0
    }
    
    # Process all projects and calculate totals
    metrics_list = []
    for project_key, data in projects_data.items():
        metrics = data['metrics']
        is_active = data.get('is_active', True)
        is_marked = data.get('is_marked_for_deletion', False)
        
        # Count active/inactive projects
        if is_active:
            total_metrics['active_count'] += 1
        else:
            total_metrics['inactive_count'] += 1
        
        # Add metrics to list for display
        metrics_entry = {
            'project_key': project_key,
            'project_name': data['name'],
            'is_active': is_active,
            'is_marked_for_deletion': is_marked,
            'quality_score': analyzer.calculate_quality_score(metrics),
            'update_interval': get_project_update_interval(project_key),
            'last_update': get_last_update_timestamp(project_key),
            **metrics
        }
        metrics_list.append(metrics_entry)
        
        # Add to totals
        for metric in ['ncloc', 'bugs', 'vulnerabilities', 'code_smells', 'sqale_index']:
            if metric in metrics:
                total_metrics[metric] += float(metrics[metric])
    
    # Display organization totals
    st.markdown(f"""
        <div class="totals-card">
            <h3 style="color: #FAFAFA;">📊 Organization Totals</h3>
            <div style="color: #A0AEC0; margin-bottom: 1rem;">
                Projects: {total_metrics['active_count']} Active, {total_metrics['inactive_count']} Inactive
            </div>
            <div class="metric-grid">
                <div class="metric-item">
                    <div class="metric-title">Total Lines of Code</div>
                    <div class="metric-value">{format_code_lines(total_metrics['ncloc'])} 📏</div>
                </div>
                <div class="metric-item">
                    <div class="metric-title">Total Technical Debt</div>
                    <div class="metric-value">{format_technical_debt(total_metrics['sqale_index'])} ⏱️</div>
                </div>
                <div class="metric-item">
                    <div class="metric-title">Total Issues</div>
                    <div class="metric-value">
                        🐛 {int(total_metrics['bugs'])} 
                        ⚠️ {int(total_metrics['vulnerabilities'])} 
                        🔧 {int(total_metrics['code_smells'])}
                    </div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Sort projects by active status first, then quality score
    df = pd.DataFrame(metrics_list)
    df = df.sort_values(['is_active', 'quality_score'], ascending=[False, False])
    
    # Display individual project cards
    for _, row in df.iterrows():
        status_icon = "🗑️" if row['is_marked_for_deletion'] else "⚠️" if not row['is_active'] else "✅"
        status_class = "status-active" if row['is_active'] else "status-inactive"
        status_text = "Active" if row['is_active'] else "Inactive"
        card_class = "project-card" + (" metric-card-inactive" if not row['is_active'] else "")
        
        interval_display = format_update_interval(row['update_interval'])
        last_update_display = format_last_update(row['last_update'])
        
        st.markdown(f"""
            <div class="{card_class}">
                <h3 style="color: #FAFAFA;">
                    {status_icon} {row['project_name']}
                    <span class="project-status {status_class}">{status_text}</span>
                </h3>
                <p style="color: #A0AEC0;">Quality Score: {row['quality_score']:.1f}/100</p>
                <div class="update-interval">
                    <span>⏱️ Update interval: {interval_display}</span>
                    <span>•</span>
                    <span>🕒 {last_update_display}</span>
                </div>
                {'<div class="data-freshness">Using historical data from last seen date</div>' if not row['is_active'] else ''}
                <div class="metric-grid">
                    <div class="metric-item">
                        <div class="metric-title">Lines of Code</div>
                        <div class="metric-value">{format_code_lines(row['ncloc'])} 📏</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-title">Technical Debt</div>
                        <div class="metric-value">{format_technical_debt(row['sqale_index'])} ⏱️</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-title">Bugs</div>
                        <div class="metric-value">{int(row['bugs'])} 🐛</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-title">Vulnerabilities</div>
                        <div class="metric-value">{int(row['vulnerabilities'])} ⚠️</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-title">Code Smells</div>
                        <div class="metric-value">{int(row['code_smells'])} 🔧</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-title">Coverage</div>
                        <div class="metric-value">{row['coverage']:.1f}% 📊</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-title">Duplication</div>
                        <div class="metric-value">{row['duplicated_lines_density']:.1f}% 📝</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

[Rest of the file remains the same...]
