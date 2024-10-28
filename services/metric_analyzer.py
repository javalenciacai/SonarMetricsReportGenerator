import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class MetricAnalyzer:
    @staticmethod
    def calculate_trend(metrics_data, metric_name):
        """Calculate trend for a specific metric"""
        df = pd.DataFrame(metrics_data)
        if df.empty or metric_name not in df.columns:
            return None
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # Calculate simple moving average
        df[f'{metric_name}_sma'] = df[metric_name].rolling(window=3).mean()
        
        # Calculate trend direction
        last_values = df[metric_name].tail(3)
        if len(last_values) < 3:
            return "insufficient_data"
            
        trend = "stable"
        if last_values.is_monotonic_increasing:
            trend = "increasing"
        elif last_values.is_monotonic_decreasing:
            trend = "decreasing"
            
        return {
            'trend': trend,
            'current_value': float(last_values.iloc[-1]),
            'avg_value': float(last_values.mean()),
            'min_value': float(last_values.min()),
            'max_value': float(last_values.max())
        }

    @staticmethod
    def calculate_period_comparison(metrics_data, metric_name, days=7):
        """Compare metric values between two time periods"""
        df = pd.DataFrame(metrics_data)
        if df.empty or metric_name not in df.columns:
            return None
            
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        current_date = df['timestamp'].max()
        period_start = current_date - timedelta(days=days)
        
        current_period = df[df['timestamp'] > period_start][metric_name]
        previous_period = df[df['timestamp'] <= period_start][metric_name]
        
        if current_period.empty or previous_period.empty:
            return None
            
        current_avg = current_period.mean()
        previous_avg = previous_period.mean()
        
        change_percentage = ((current_avg - previous_avg) / previous_avg * 100) if previous_avg != 0 else 0
        
        return {
            'current_period_avg': float(current_avg),
            'previous_period_avg': float(previous_avg),
            'change_percentage': float(change_percentage),
            'improved': change_percentage < 0 if metric_name in ['bugs', 'vulnerabilities', 'code_smells'] else change_percentage > 0
        }

    @staticmethod
    def calculate_quality_score(metrics_dict):
        """Calculate an overall quality score based on multiple metrics"""
        weights = {
            'bugs': -2,
            'vulnerabilities': -3,
            'code_smells': -1,
            'coverage': 2,
            'duplicated_lines_density': -1
        }
        
        score = 100  # Start with perfect score
        
        for metric, weight in weights.items():
            if metric in metrics_dict:
                value = float(metrics_dict[metric])
                if metric == 'coverage':
                    score += (value - 80) * weight if value > 80 else -40  # Penalty for low coverage
                elif metric == 'duplicated_lines_density':
                    score += (20 - value) * abs(weight) if value < 20 else -20  # Penalty for high duplication
                else:
                    score += -value * abs(weight)  # Penalty for issues
                    
        return max(0, min(100, score))  # Ensure score is between 0 and 100

    @staticmethod
    def get_metric_status(metrics_dict):
        """Determine status for each metric based on thresholds"""
        thresholds = {
            'bugs': {'good': 0, 'warning': 3, 'critical': 5},
            'vulnerabilities': {'good': 0, 'warning': 2, 'critical': 4},
            'code_smells': {'good': 10, 'warning': 50, 'critical': 100},
            'coverage': {'critical': 50, 'warning': 70, 'good': 80},
            'duplicated_lines_density': {'good': 3, 'warning': 5, 'critical': 10}
        }
        
        status = {}
        for metric, value in metrics_dict.items():
            if metric not in thresholds:
                continue
                
            threshold = thresholds[metric]
            value = float(value)
            
            if metric in ['coverage']:
                if value >= threshold['good']:
                    status[metric] = 'good'
                elif value >= threshold['warning']:
                    status[metric] = 'warning'
                else:
                    status[metric] = 'critical'
            else:
                if value <= threshold['good']:
                    status[metric] = 'good'
                elif value <= threshold['warning']:
                    status[metric] = 'warning'
                else:
                    status[metric] = 'critical'
                    
        return status
