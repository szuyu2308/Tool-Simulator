# utils/subprocess_helper.py
"""
Subprocess Helper - Wrapper for subprocess calls with proper windowed mode support
"""

import subprocess
import sys

# Windows CREATE_NO_WINDOW flag
if sys.platform == 'win32':
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0


def run_hidden(*args, **kwargs):
    """
    Wrapper for subprocess.run() that works in windowed mode
    Automatically adds CREATE_NO_WINDOW flag on Windows
    
    Usage: Same as subprocess.run()
        run_hidden(["adb", "devices"], capture_output=True)
    """
    if sys.platform == 'win32':
        # Add creationflags if not specified
        if 'creationflags' not in kwargs:
            kwargs['creationflags'] = CREATE_NO_WINDOW
        else:
            # Combine with existing flags
            kwargs['creationflags'] |= CREATE_NO_WINDOW
    
    return subprocess.run(*args, **kwargs)


def Popen_hidden(*args, **kwargs):
    """
    Wrapper for subprocess.Popen() that works in windowed mode
    Automatically adds CREATE_NO_WINDOW flag on Windows
    
    Usage: Same as subprocess.Popen()
        Popen_hidden(["cmd"], stdout=subprocess.PIPE)
    """
    if sys.platform == 'win32':
        # Add creationflags if not specified
        if 'creationflags' not in kwargs:
            kwargs['creationflags'] = CREATE_NO_WINDOW
        else:
            # Combine with existing flags
            kwargs['creationflags'] |= CREATE_NO_WINDOW
    
    return subprocess.Popen(*args, **kwargs)


def call_hidden(*args, **kwargs):
    """
    Wrapper for subprocess.call() that works in windowed mode
    Automatically adds CREATE_NO_WINDOW flag on Windows
    
    Usage: Same as subprocess.call()
        call_hidden(["adb", "devices"])
    """
    if sys.platform == 'win32':
        # Add creationflags if not specified
        if 'creationflags' not in kwargs:
            kwargs['creationflags'] = CREATE_NO_WINDOW
        else:
            # Combine with existing flags
            kwargs['creationflags'] |= CREATE_NO_WINDOW
    
    return subprocess.call(*args, **kwargs)


def check_output_hidden(*args, **kwargs):
    """
    Wrapper for subprocess.check_output() that works in windowed mode
    Automatically adds CREATE_NO_WINDOW flag on Windows
    
    Usage: Same as subprocess.check_output()
        check_output_hidden(["adb", "devices"])
    """
    if sys.platform == 'win32':
        # Add creationflags if not specified
        if 'creationflags' not in kwargs:
            kwargs['creationflags'] = CREATE_NO_WINDOW
        else:
            # Combine with existing flags
            kwargs['creationflags'] |= CREATE_NO_WINDOW
    
    return subprocess.check_output(*args, **kwargs)
