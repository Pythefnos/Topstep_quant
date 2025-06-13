#!/usr/bin/env python3
"""
Script to find and compile all Python files in the project directory.
This replaces the Unix 'find' command which is not available in the current shell.
"""

import os
import py_compile
import sys

def compile_python_files(root_dir='.'):
    """
    Walk through directory tree and compile all .py files found.
    
    Args:
        root_dir (str): Root directory to start search from
    
    Returns:
        tuple: (success_count, error_count, errors)
    """
    success_count = 0
    error_count = 0
    errors = []
    
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    py_compile.compile(file_path, doraise=True)
                    print(f"✓ Compiled: {file_path}")
                    success_count += 1
                except py_compile.PyCompileError as e:
                    print(f"✗ Error compiling {file_path}: {e}")
                    errors.append((file_path, str(e)))
                    error_count += 1
                except Exception as e:
                    print(f"✗ Unexpected error compiling {file_path}: {e}")
                    errors.append((file_path, str(e)))
                    error_count += 1
    
    return success_count, error_count, errors

if __name__ == "__main__":
    print("Compiling all Python files in the project...")
    print("-" * 50)
    
    success_count, error_count, errors = compile_python_files()
    
    print("-" * 50)
    print(f"Compilation complete:")
    print(f"  ✓ Successfully compiled: {success_count} files")
    print(f"  ✗ Failed to compile: {error_count} files")
    
    if errors:
        print("\nErrors encountered:")
        for file_path, error in errors:
            print(f"  {file_path}: {error}")
        sys.exit(1)
    else:
        print("\nAll Python files compiled successfully!")
        sys.exit(0)