def parse_metric_value(value):
    """Convert metric values to appropriate types"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def format_timestamp(timestamp):
    """Format timestamp for display in UTC"""
    if timestamp.tzinfo is None:
        from datetime import timezone
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")

def format_code_lines(lines):
    """Format lines of code with K/M suffixes"""
    try:
        lines = float(lines)
        if lines >= 1_000_000:
            return f"{lines/1_000_000:.1f}M"
        elif lines >= 1_000:
            return f"{lines/1_000:.1f}K"
        return str(int(lines))
    except (ValueError, TypeError):
        return "0"

def format_technical_debt(minutes):
    """Format technical debt minutes into readable format"""
    try:
        minutes = float(minutes)
        if minutes < 60:
            return f"{int(minutes)}min"
        elif minutes < 1440:  # Less than 24 hours
            hours = minutes / 60
            return f"{hours:.1f}h"
        else:
            days = minutes / 1440
            return f"{days:.1f}d"
    except (ValueError, TypeError):
        return "0min"
