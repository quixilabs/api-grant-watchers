#!/usr/bin/env python3
"""
Format application logs for better readability.

Usage:
    python run.py > app.log
    python format_logs.py app.log
    python format_logs.py app.log --filter "keyword"
    python format_logs.py app.log --level INFO
    python format_logs.py app.log --module app.utils.supabase
"""

import sys
import re
import json
import argparse
from datetime import datetime
import os

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def format_log_line(line):
    """Format a single log line with colors and indentation."""
    # Match standard log level pattern (INFO:app.module:Message)
    level_match = re.match(r'^([A-Z]+):([^:]+):(.*)', line)
    if level_match:
        level, module, message = level_match.groups()
        
        # Color based on log level
        if level == "DEBUG":
            level_color = Colors.BLUE
        elif level == "INFO":
            level_color = Colors.GREEN
        elif level == "WARNING":
            level_color = Colors.YELLOW
        elif level == "ERROR":
            level_color = Colors.RED
        elif level == "CRITICAL":
            level_color = Colors.RED + Colors.BOLD
        else:
            level_color = Colors.ENDC
            
        # Format the line
        formatted_line = f"{level_color}{level.ljust(8)}{Colors.ENDC} "
        formatted_line += f"{Colors.CYAN}{module.strip()}{Colors.ENDC}: "
        formatted_line += f"{message.strip()}"
        
        return formatted_line
    
    # Match timestamp format (2023-04-15 12:34:56,789 - module - LEVEL - Message)
    timestamp_match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - ([^-]+) - ([A-Z]+) - (.*)', line)
    if timestamp_match:
        timestamp, module, level, message = timestamp_match.groups()
        
        # Color based on log level
        if level == "DEBUG":
            level_color = Colors.BLUE
        elif level == "INFO":
            level_color = Colors.GREEN
        elif level == "WARNING":
            level_color = Colors.YELLOW
        elif level == "ERROR":
            level_color = Colors.RED
        elif level == "CRITICAL":
            level_color = Colors.RED + Colors.BOLD
        else:
            level_color = Colors.ENDC
            
        # Format the line
        formatted_line = f"{Colors.HEADER}{timestamp}{Colors.ENDC} "
        formatted_line += f"{level_color}{level.ljust(8)}{Colors.ENDC} "
        formatted_line += f"{Colors.CYAN}{module.strip()}{Colors.ENDC}: "
        formatted_line += f"{message.strip()}"
        
        return formatted_line
    
    # Match HTTP request pattern
    http_match = re.search(r'HTTP Request: ([A-Z]+) (.*?) "(HTTP/[\d.]+ [\d]+ .*?)"', line)
    if http_match:
        method, url, status = http_match.groups()
        status_code = re.search(r'HTTP/[\d.]+ ([\d]+)', status)
        
        # Color status code based on response
        if status_code:
            code = int(status_code.group(1))
            if code < 300:
                status_color = Colors.GREEN
            elif code < 400:
                status_color = Colors.YELLOW
            else:
                status_color = Colors.RED
                
            formatted_line = f"{Colors.CYAN}HTTP{Colors.ENDC}: "
            formatted_line += f"{Colors.BOLD}{method}{Colors.ENDC} {url} "
            formatted_line += f"{status_color}\"{status}\"{Colors.ENDC}"
            
            return formatted_line
    
    # Match IP address pattern (common in FastAPI logs)
    ip_match = re.search(r'([\d\.]+): \d+ - "([A-Z]+) ([^"]+) HTTP/[\d\.]+" (\d+)', line)
    if ip_match:
        ip, method, path, status_code = ip_match.groups()
        
        # Color status code based on response
        code = int(status_code)
        if code < 300:
            status_color = Colors.GREEN
        elif code < 400:
            status_color = Colors.YELLOW
        else:
            status_color = Colors.RED
            
        formatted_line = f"{Colors.CYAN}REQUEST{Colors.ENDC}: "
        formatted_line += f"{Colors.BOLD}{method}{Colors.ENDC} {path} "
        formatted_line += f"{status_color}{status_code}{Colors.ENDC} from {ip}"
        
        return formatted_line
    
    # Highlight errors
    if "Error" in line or "error" in line or "ERROR" in line or "Exception" in line or "exception" in line:
        return f"{Colors.RED}{line.strip()}{Colors.ENDC}"
    
    # Highlight warnings
    if "Warning" in line or "warning" in line or "WARNING" in line:
        return f"{Colors.YELLOW}{line.strip()}{Colors.ENDC}"
    
    # Highlight successful operations
    if "Successfully" in line or "Success" in line or "success" in line:
        return f"{Colors.GREEN}{line.strip()}{Colors.ENDC}"
    
    # Handle RuntimeWarning and other non-standard formats
    if "RuntimeWarning:" in line:
        return f"{Colors.YELLOW}{line.strip()}{Colors.ENDC}"
        
    # Return the original line if no pattern matches
    return line.strip()

def extract_log_info(line):
    """Extract log level and module from a log line for filtering."""
    # Try standard format first
    level_match = re.match(r'^([A-Z]+):([^:]+):(.*)', line)
    if level_match:
        level, module, _ = level_match.groups()
        return level, module
    
    # Try timestamp format
    timestamp_match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - ([^-]+) - ([A-Z]+) - (.*)', line)
    if timestamp_match:
        _, module, level, _ = timestamp_match.groups()
        return level, module
    
    # Default values if no match
    return None, None

def should_include_line(line, filter_text=None, level_filter=None, module_filter=None):
    """Determine if a line should be included based on filters."""
    # If no filters are set, include all lines
    if not filter_text and not level_filter and not module_filter:
        return True
    
    # Apply text filter
    if filter_text and filter_text.lower() not in line.lower():
        return False
    
    # Extract log level and module for further filtering
    level, module = extract_log_info(line)
    
    # Apply level filter
    if level_filter and level and level != level_filter:
        return False
    
    # Apply module filter
    if module_filter and module and module_filter not in module:
        return False
    
    return True

def format_logs(log_file, filter_text=None, level_filter=None, module_filter=None):
    """Format logs from a file for better readability."""
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # Apply filters
        filtered_lines = [line for line in lines if should_include_line(line, filter_text, level_filter, module_filter)]
        
        # Print header with filter information
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
        header_text = "FORMATTED APPLICATION LOGS"
        if filter_text or level_filter or module_filter:
            filters = []
            if filter_text:
                filters.append(f"text='{filter_text}'")
            if level_filter:
                filters.append(f"level='{level_filter}'")
            if module_filter:
                filters.append(f"module='{module_filter}'")
            header_text += f" (Filtered by: {', '.join(filters)})"
        print(f"{Colors.HEADER}{Colors.BOLD}{header_text:^80}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")
        
        # Print filtered and formatted lines
        if filtered_lines:
            for line in filtered_lines:
                if line.strip():  # Skip empty lines
                    print(format_log_line(line))
        else:
            print(f"{Colors.YELLOW}No log entries match the specified filters.{Colors.ENDC}")
                
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'END OF LOGS':^80}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")
                
    except FileNotFoundError:
        print(f"{Colors.RED}Error: Log file '{log_file}' not found.{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.RED}Error formatting logs: {str(e)}{Colors.ENDC}")
        sys.exit(1)

def main():
    """Main function to process command line arguments."""
    parser = argparse.ArgumentParser(description="Format application logs for better readability")
    parser.add_argument("log_file", help="Path to the log file to format")
    parser.add_argument("--filter", "-f", help="Filter logs by keyword")
    parser.add_argument("--level", "-l", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], 
                        help="Filter logs by level")
    parser.add_argument("--module", "-m", help="Filter logs by module name")
    
    args = parser.parse_args()
    
    format_logs(args.log_file, args.filter, args.level, args.module)

if __name__ == "__main__":
    main() 