import streamlit as st
import pandas as pd
from services.metric_analyzer import MetricAnalyzer
from utils.helpers import format_code_lines, format_technical_debt
from database.schema import get_update_preferences
from database.connection import execute_query
from datetime import datetime, timezone

def format_update_interval(seconds):
    """Format update interval in a human-readable way"""
    if seconds >= 86400:
        return f"{seconds//86400}d"
    elif seconds >= 3600:
        return f"{seconds//3600}h"
    elif seconds >= 60:
        return f"{seconds//60}m"
    return f"{seconds}s"

def format_last_update(timestamp):
    """Format last update timestamp in a human-readable way"""
    if not timestamp:
        return "No updates yet"
    
    try:
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        # Convert to UTC if not already
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = now - timestamp
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds >= 3600:
            return f"{diff.seconds//3600}h ago"
        elif diff.seconds >= 60:
            return f"{diff.seconds//60}m ago"
        return f"{diff.seconds}s ago"
    except (ValueError, TypeError) as e:
        print(f"Error formatting timestamp: {str(e)}")
        return "Invalid timestamp"

# Rest of the file remains the same
