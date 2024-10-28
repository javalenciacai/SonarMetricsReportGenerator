def parse_metric_value(value):
    """Convert metric values to appropriate types"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def format_timestamp(timestamp):
    """Format timestamp for display"""
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")
