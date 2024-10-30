class MetricAnalyzer:
    def calculate_quality_score(self, metrics):
        """Calculate quality score (0-100) with consistent timestamp handling"""
        try:
            # Quality score weights
            weights = {
                'coverage': 2.0,          # Higher coverage is good
                'bugs': -2.0,             # Bugs reduce score
                'vulnerabilities': -3.0,   # Vulnerabilities heavily reduce score
                'code_smells': -1.0,      # Code smells slightly reduce score
                'duplicated_lines_density': -1.0  # Duplication reduces score
            }
            
            # Initialize base score
            score = 100.0
            
            # Add weighted contributions
            if metrics.get('coverage'):
                score += weights['coverage'] * float(metrics['coverage'])
            if metrics.get('bugs'):
                score += weights['bugs'] * float(metrics['bugs'])
            if metrics.get('vulnerabilities'):
                score += weights['vulnerabilities'] * float(metrics['vulnerabilities'])
            if metrics.get('code_smells'):
                score += weights['code_smells'] * float(metrics['code_smells']) / 100
            if metrics.get('duplicated_lines_density'):
                score += weights['duplicated_lines_density'] * float(metrics['duplicated_lines_density']) / 10
            
            # Ensure score is between 0 and 100
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            print(f"Error calculating quality score: {str(e)}")
            return 0.0
