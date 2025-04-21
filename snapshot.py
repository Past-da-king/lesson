#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Standalone Codebase Snapshot Tool (Concise Commands)

This script provides two main functions, runnable from the command line:
1.  fm <folder>: Creates a single Markdown file snapshot from a source code folder.
2.  mf <markdown_file>: Recreates a folder structure from a Markdown snapshot file.

Usage:
  # Create snapshot FROM 'my_project_folder' TO 'snapshot.md' (Folder -> Markdown)
  python this_script.py fm ./my_project_folder -o snapshot.md

  # Create snapshot with additional ignore patterns
  python this_script.py fm ./proj -o out.md --ignore "*.log" --ignore "temp/"

  # Recreate folder structure FROM 'snapshot.md' TO 'recreated_project' (Markdown -> Folder)
  python this_script.py mf snapshot.md -o ./recreated_project
"""

import os
import mimetypes
import fnmatch
import platform
import argparse
import sys

# --- Configuration ---
ENCODING = 'utf-8'

# --- Default Ignore Patterns ---
DEFAULT_IGNORE_PATTERNS = [
    '.git', '.gitignore', '.gitattributes', '.svn', '.hg', 'node_modules',
    'bower_components', 'venv', '.venv', 'env', '.env', '.env.*', '*.pyc',
    '__pycache__', 'build', 'dist', 'target', '*.o', '*.so', '*.dll', '*.exe',
    '*.class', '*.jar', '*.war', '*.log', '*.tmp', '*.swp', '*.swo', '.DS_Store',
    'Thumbs.db', '.vscode', '.idea', '*.sublime-project', '*.sublime-workspace',
    '*.zip', '*.tar', '*.gz', '*.rar', 'credentials.*', 'config.local.*',
    'settings.local.py',
]

# --- Core Helper Functions (No Changes Here) ---

def is_ignored(relative_path, ignore_patterns):
    normalized_path = relative_path.replace("\\", "/")
    basename = os.path.basename(normalized_path)
    is_case_sensitive_fs = platform.system() != "Windows"
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(basename, pattern) or \
           (not is_case_sensitive_fs and fnmatch.fnmatch(basename.lower(), pattern.lower())):
            return True
        if fnmatch.fnmatch(normalized_path, pattern) or \
           (not is_case_sensitive_fs and fnmatch.fnmatch(normalized_path.lower(), pattern.lower())):
            return True
    return False

def guess_language(filepath):
    mimetypes.init()
    mime_type, _ = mimetypes.guess_type(filepath)
    if mime_type:
        lang_map_mime = {
            "text/x-python": "python", "application/x-python-code": "python",
            "text/javascript": "javascript", "application/javascript": "javascript",
            "text/html": "html", "text/css": "css", "application/json": "json",
            "application/xml": "xml", "text/xml": "xml",
            "text/x-java-source": "java", "text/x-java": "java",
            "text/x-csrc": "c", "text/x-c": "c", "text/x-c++src": "cpp", "text/x-c++": "cpp",
            "application/x-sh": "bash", "text/x-shellscript": "bash",
            "text/markdown": "markdown", "text/x-yaml": "yaml", "application/x-yaml": "yaml",
            "text/plain": ""
        }
        if mime_type in lang_map_mime: return lang_map_mime[mime_type]
        if mime_type.startswith("text/"): return ""
    _, ext = os.path.splitext(filepath.lower())
    lang_map_ext = {
        ".py": "python", ".pyw": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
        ".html": "html", ".htm": "html", ".css": "css", ".java": "java", ".cpp": "cpp", ".cxx": "cpp",
        ".cc": "cpp", ".hpp": "cpp", ".hxx": "cpp", ".c": "c", ".h": "c", ".cs": "csharp", ".php": "php",
        ".rb": "ruby", ".go": "go", ".rs": "rust", ".ts": "typescript", ".tsx": "typescript",
        ".json": "json", ".xml": "xml", ".yaml": "yaml", ".yml": "yaml", ".sh": "bash", ".bash": "bash",
        ".sql": "sql", ".md": "markdown", ".markdown": "markdown", ".txt": ""
    }
    return lang_map_ext.get(ext, "")

def write_code_to_file(output_dir, relative_filepath, code_lines, encoding=ENCODING):
    safe_relative_path = os.path.normpath(relative_filepath).replace("\\", "/")
    if safe_relative_path.startswith("..") or os.path.isabs(safe_relative_path):
        print(f"[WRITE] [WARN] Skipping potentially unsafe path: {relative_filepath}")
        return False
    abs_output_dir = os.path.abspath(output_dir)
    full_path = os.path.join(abs_output_dir, safe_relative_path)
    abs_full_path = os.path.abspath(full_path)
    if not abs_full_path.startswith(abs_output_dir + os.path.sep) and abs_full_path != abs_output_dir:
        print(f"[WRITE] [ERROR] Security Error: Attempted write outside target directory: {relative_filepath} -> {abs_full_path}")
        return False
    dir_name = os.path.dirname(full_path)
    try:
        if dir_name: os.makedirs(dir_name, exist_ok=True)
        if os.path.isdir(full_path):
             print(f"[WRITE] [ERROR] Cannot write file. Path exists and is a directory: {full_path}")
             return False
        with open(full_path, "w", encoding=encoding) as outfile:
            outfile.writelines(code_lines)
        return True
    except OSError as e:
        print(f"[WRITE] [ERROR] OS Error writing file {full_path}: {e}")
        return False
    except Exception as e:
        print(f"[WRITE] [ERROR] General Error writing file {full_path}: {e}")
        return False

# --- Main Logic Functions (No Changes Here) ---

def create_codebase_snapshot(root_dir, output_file, encoding=ENCODING, base_ignore_patterns=DEFAULT_IGNORE_PATTERNS, user_ignore_patterns=[]):
    processed_files_count = 0
    ignored_items_count = 0
    errors = []
    all_ignore_patterns = list(set(base_ignore_patterns + user_ignore_patterns))
    abs_root = os.path.abspath(root_dir)
    if not os.path.isdir(abs_root):
        print(f"[ERROR] Source directory not found or not a directory: {abs_root}", file=sys.stderr)
        return False, 0, 0, ["Source directory not found."]

    print("-" * 60)
    print(f"Starting snapshot creation (Folder -> Markdown):")
    print(f"  Source: {abs_root}")
    print(f"  Output: {output_file}")
    print(f"  Ignoring: {all_ignore_patterns}")
    print("-" * 60)
    try:
        with open(output_file, "w", encoding=encoding) as md_file:
            md_file.write("# Codebase Snapshot\n\n")
            md_file.write(f"Source Directory: `{os.path.basename(abs_root)}`\n\n")
            for dirpath, dirnames, filenames in os.walk(abs_root, topdown=True):
                dirs_to_remove = set()
                for d in dirnames:
                    rel_dir_path = os.path.relpath(os.path.join(dirpath, d), abs_root)
                    if is_ignored(rel_dir_path, all_ignore_patterns): dirs_to_remove.add(d)
                if dirs_to_remove:
                    ignored_items_count += len(dirs_to_remove)
                    dirnames[:] = [d for d in dirnames if d not in dirs_to_remove]
                filenames.sort()
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    relative_filepath = os.path.relpath(filepath, abs_root).replace("\\", "/")
                    if is_ignored(relative_filepath, all_ignore_patterns):
                        ignored_items_count += 1; continue
                    processed_files_count += 1
                    print(f"[PROCESS] Adding: {relative_filepath}")
                    md_file.write(f"## {relative_filepath}\n\n")
                    try:
                        try:
                             with open(filepath, "r", encoding=encoding) as f_content: content = f_content.read()
                             language = guess_language(filepath)
                             md_file.write(f"```{language}\n{content}\n```\n\n")
                        except UnicodeDecodeError:
                             md_file.write("```\n**Note:** File appears to be binary or uses an incompatible encoding.\nContent not displayed.\n```\n\n")
                             print(f"[WARN] Binary or non-{encoding} file skipped content: {relative_filepath}")
                        except Exception as read_err:
                             errors.append(f"Error reading file '{relative_filepath}': {read_err}")
                             md_file.write(f"```\n**Error reading file:** {read_err}\n```\n\n")
                             print(f"[ERROR] Could not read file: {relative_filepath} - {read_err}")
                    except Exception as e:
                        errors.append(f"Error processing file '{relative_filepath}': {e}")
                        md_file.write(f"```\n**Error processing file:** {e}\n```\n\n")
                        print(f"[ERROR] Processing failed for: {relative_filepath} - {e}")
    except IOError as e:
        print(f"[ERROR] Failed to write snapshot file '{output_file}': {e}", file=sys.stderr)
        return False, processed_files_count, ignored_items_count, [f"IOError writing snapshot: {e}"]
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred during snapshot generation: {e}", file=sys.stderr)
        return False, processed_files_count, ignored_items_count, [f"Unexpected error: {e}"]
    print("-" * 60)
    print(f"Snapshot creation finished.")
    print(f"  Processed: {processed_files_count} files")
    print(f"  Ignored:   {ignored_items_count} items")
    if errors: print(f"  Errors:    {len(errors)}"); [print(f"    - {err}") for err in errors]
    print("-" * 60)
    return True, processed_files_count, ignored_items_count, errors

def extract_codebase(md_file, output_dir, encoding=ENCODING):
    created_files_count = 0; errors = []; file_write_attempts = 0
    abs_output_dir = os.path.abspath(output_dir)
    if not os.path.isfile(md_file):
        print(f"[ERROR] Snapshot file not found: {md_file}", file=sys.stderr)
        return False, 0, ["Snapshot file not found."]
    print("-" * 60); print(f"Starting codebase extraction (Markdown -> Folder):"); print(f"  Snapshot: {md_file}"); print(f"  Output Directory: {abs_output_dir}"); print("-" * 60)
    try:
        os.makedirs(abs_output_dir, exist_ok=True); print(f"[INFO] Ensured output directory exists: {abs_output_dir}")
    except OSError as e: print(f"[ERROR] Failed to create output directory '{abs_output_dir}': {e}", file=sys.stderr); return False, 0, [f"Failed to create output directory: {e}"]
    try:
        with open(md_file, "r", encoding=encoding) as f: lines = f.readlines()
    except Exception as e: print(f"[ERROR] Failed to read snapshot file '{md_file}': {e}", file=sys.stderr); return False, 0, [f"Failed to read snapshot file: {e}"]
    relative_filepath = None; in_code_block = False; code_lines = []; skip_block_content = False
    for line_num, line in enumerate(lines, 1):
        line_stripped = line.strip()
        if line_stripped.startswith("## "):
            if relative_filepath and code_lines and not skip_block_content:
                file_write_attempts += 1
                if write_code_to_file(abs_output_dir, relative_filepath, code_lines, encoding): created_files_count += 1
                else: errors.append(f"Failed write: {relative_filepath} (ended near line {line_num})")
            code_lines = []; relative_filepath = None; in_code_block = False; skip_block_content = False
            new_relative_filepath = line[3:].strip().strip('/').strip('\\')
            if not new_relative_filepath: errors.append(f"Warning: Found '##' header without a filepath on line {line_num}. Skipping.")
            else: relative_filepath = new_relative_filepath
        elif line_stripped.startswith("```"):
            if in_code_block:
                in_code_block = False
                if relative_filepath and code_lines and not skip_block_content:
                     file_write_attempts += 1
                     if write_code_to_file(abs_output_dir, relative_filepath, code_lines, encoding): created_files_count += 1
                     else: errors.append(f"Failed write: {relative_filepath} (block ended line {line_num})")
                elif skip_block_content: pass
                elif relative_filepath and not code_lines:
                    file_write_attempts += 1; print(f"[WARN] Empty code block for {relative_filepath} on line {line_num}. Creating empty file.")
                    if write_code_to_file(abs_output_dir, relative_filepath, [], encoding): created_files_count += 1
                    else: errors.append(f"Failed write (empty): {relative_filepath}")
                elif not relative_filepath and code_lines: errors.append(f"Warning: Code block found ending on line {line_num} without a preceding '## filepath' header. Content ignored.")
                code_lines = []; skip_block_content = False
            else: in_code_block = True; code_lines = []; skip_block_content = False
        elif in_code_block:
            if line_stripped.startswith("**Note:") or line_stripped.startswith("**Error reading file:") or line_stripped.startswith("**Binary File:"):
                 skip_block_content = True; print(f"[INFO] Skipping content block for {relative_filepath} due to marker: {line_stripped[:30]}...")
            if not skip_block_content: code_lines.append(line)
    if relative_filepath and code_lines and not skip_block_content:
        file_write_attempts += 1
        if write_code_to_file(abs_output_dir, relative_filepath, code_lines, encoding): created_files_count += 1
        else: errors.append(f"Failed write (end of file): {relative_filepath}")
    elif relative_filepath and skip_block_content: pass
    print("-" * 60); print(f"Codebase extraction finished."); print(f"  Attempted writes: {file_write_attempts}"); print(f"  Successfully created: {created_files_count} files")
    if errors: print(f"  Errors/Warnings: {len(errors)}"); [print(f"    - {err}") for err in errors]
    print("-" * 60)
    return True, created_files_count, errors


# --- Command Line Interface (Modified for Positional Args) ---
def main():
    parser = argparse.ArgumentParser(
        description="Standalone Codebase Snapshot Tool. Use 'fm <folder>' or 'mf <markdown_file>'.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python %(prog)s fm ./my_project -o project_snapshot.md
  python %(prog)s mf project_snapshot.md -o ./recreated_project"""
    )

    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands: fm, mf')

    # --- Sub-parser for fm (Folder to Markdown) ---
    parser_fm = subparsers.add_parser('fm', help='Create Markdown from Folder.')
    # Positional argument for input directory
    parser_fm.add_argument('input_directory', help='Path to the source code directory.')
    # Optional argument for output file
    parser_fm.add_argument('--output', '-o', required=True, dest='output_markdown', help='Path for the output Markdown snapshot file.')
    # Optional ignore patterns (remains the same)
    parser_fm.add_argument('--ignore', action='append', default=[], help='Additional ignore patterns (glob style). Can be used multiple times.')

    # --- Sub-parser for mf (Markdown to Folder) ---
    parser_mf = subparsers.add_parser('mf', help='Create Folder from Markdown.')
    # Positional argument for input markdown file
    parser_mf.add_argument('input_markdown', help='Path to the input Markdown snapshot file.')
    # Optional argument for output directory
    parser_mf.add_argument('--output', '-o', required=True, dest='output_directory', help='Path to the directory where the codebase will be recreated.')

    args = parser.parse_args()

    # --- Execute selected command ---
    if args.command == 'fm':
        print(f"Running: Folder to Markdown (fm)")
        success, processed, ignored, errors = create_codebase_snapshot(
            root_dir=args.input_directory,       # Use positional arg
            output_file=args.output_markdown,    # Use '-o' arg (renamed via dest)
            encoding=ENCODING,
            base_ignore_patterns=DEFAULT_IGNORE_PATTERNS,
            user_ignore_patterns=args.ignore
        )
        if success:
            print(f"\nSuccess! Snapshot created at: {args.output_markdown}")
            print(f"Processed {processed} files, ignored {ignored} items.")
            if errors: print(f"Completed with {len(errors)} errors/warnings during file processing.")
            sys.exit(0)
        else:
            print(f"\nFailed to create snapshot.", file=sys.stderr)
            sys.exit(1)

    elif args.command == 'mf':
        print(f"Running: Markdown to Folder (mf)")
        success, created_count, errors = extract_codebase(
            md_file=args.input_markdown,       # Use positional arg
            output_dir=args.output_directory,  # Use '-o' arg (renamed via dest)
            encoding=ENCODING
        )
        if success:
             print(f"\nSuccess! Codebase extracted to: {args.output_directory}")
             print(f"Created {created_count} files.")
             if errors: print(f"Completed with {len(errors)} errors/warnings during file writing.")
             sys.exit(0)
        else:
            print(f"\nFailed to extract codebase.", file=sys.stderr)
            sys.exit(1)

# --- Main Execution Guard ---
if __name__ == '__main__':
    main()