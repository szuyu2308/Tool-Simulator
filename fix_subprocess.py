#!/usr/bin/env python3
"""
Quick fix script to add CREATE_NO_WINDOW flag to all subprocess calls
"""

import re
import sys

def fix_subprocess_calls(filepath):
    """Add creationflags=CREATE_NO_WINDOW to all subprocess.run() calls"""
    
    print(f"Processing {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to match subprocess.run(...) without creationflags
    # Match multi-line subprocess.run calls
    pattern = r'(subprocess\.run\s*\([^)]+?)(\s*\))'
    
    def add_creation_flag(match):
        call = match.group(1)
        close = match.group(2)
        
        # Skip if already has creationflags
        if 'creationflags' in call:
            return match.group(0)
        
        # Add creationflags before closing paren
        # Check if last char before ) is a newline/space or comma
        if call.rstrip().endswith(','):
            # Already has comma
            fixed = f"{call}\n                creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0{close}"
        else:
            # Add comma first
            fixed = f"{call},\n                creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0{close}"
        
        return fixed
    
    # Apply fix
    fixed_content = re.sub(pattern, add_creation_flag, content, flags=re.DOTALL)
    
    # Count changes
    original_count = len(re.findall(r'subprocess\.run', content))
    fixed_count = len(re.findall(r'creationflags=CREATE_NO_WINDOW', fixed_content))
    
    print(f"  Found {original_count} subprocess.run() calls")
    print(f"  Added CREATE_NO_WINDOW to {fixed_count} calls")
    
    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print(f"  ✅ Fixed {filepath}\n")

if __name__ == '__main__':
    files_to_fix = [
        'ui/main_ui.py',
        'core/wait_actions.py',
    ]
    
    for filepath in files_to_fix:
        try:
            fix_subprocess_calls(filepath)
        except Exception as e:
            print(f"  ❌ Error fixing {filepath}: {e}\n")
    
    print("Done! Please review changes and rebuild.")
