#!/usr/bin/env python3
"""
Code Collection Script
Collects all code files in the current directory and outputs them in a format suitable for LLM analysis.
"""

import os
import glob
from pathlib import Path
from datetime import datetime

def collect_all_codes(directory=".", output_file="collected_codes.txt"):
    """Collect all code files and their contents."""
    
    # Common code file extensions
    code_extensions = [
        "*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.java", "*.cpp", "*.c", "*.h", 
        "*.cs", "*.php", "*.rb", "*.go", "*.rs", "*.swift", "*.kt", "*.scala",
        "*.html", "*.css", "*.scss", "*.less", "*.vue", "*.svelte",
        "*.json", "*.xml", "*.yaml", "*.yml", "*.toml", "*.ini", "*.cfg",
        "*.md", "*.txt", "*.sh", "*.bat", "*.ps1"
    ]
    
    # Files to exclude
    exclude_patterns = [
        "__pycache__", "*.pyc", "node_modules", ".git", ".vscode", 
        "*.log", "*.tmp", "*.cache", "dist", "build", ".pytest_cache",
        "collected_codes.txt"  # Don't include the output file itself
    ]
    
    collected_files = []
    
    # Get all files matching code extensions
    for extension in code_extensions:
        files = glob.glob(os.path.join(directory, extension))
        for file_path in files:
            # Skip excluded patterns
            if any(exclude in file_path for exclude in exclude_patterns):
                continue
            collected_files.append(file_path)
    
    # Also check subdirectories (one level deep)
    for subdir in os.listdir(directory):
        subdir_path = os.path.join(directory, subdir)
        if os.path.isdir(subdir_path) and not any(exclude in subdir for exclude in exclude_patterns):
            for extension in code_extensions:
                files = glob.glob(os.path.join(subdir_path, extension))
                for file_path in files:
                    if any(exclude in file_path for exclude in exclude_patterns):
                        continue
                    collected_files.append(file_path)
    
    # Sort files for consistent output
    collected_files.sort()
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        # Header
        f.write("=" * 80 + "\n")
        f.write("COMPLETE CODEBASE COLLECTION\n")
        f.write("=" * 80 + "\n")
        f.write(f"Directory: {os.path.abspath(directory)}\n")
        f.write(f"Total files found: {len(collected_files)}\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        # File contents
        for file_path in collected_files:
            relative_path = os.path.relpath(file_path, directory)
            
            f.write(f"📁 FILE: {relative_path}\n")
            f.write("-" * 60 + "\n")
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read()
                    f.write(content)
            except Exception as e:
                f.write(f"❌ Error reading file: {e}\n")
            
            f.write("\n")
            f.write("=" * 80 + "\n\n")
    
    # Print summary to console
    print("🔍 Code collection completed!")
    print(f"📂 Directory scanned: {os.path.abspath(directory)}")
    print(f"📄 Files collected: {len(collected_files)}")
    print(f"💾 Output saved to: {output_file}")
    print("\nFiles included:")
    for file_path in collected_files:
        relative_path = os.path.relpath(file_path, directory)
        print(f"  • {relative_path}")

if __name__ == "__main__":
    print("🔍 Collecting all code files in the current directory...")
    print()
    collect_all_codes()
    print("\n✅ Collection complete!") 