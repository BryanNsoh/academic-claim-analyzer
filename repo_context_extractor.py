import os
import datetime

EXCLUDED_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
FULL_CONTENT_EXTENSIONS = {".py", ".toml", ".dbml", ".yaml"}

def create_file_element(file_path, root_folder):
    relative_path = os.path.relpath(file_path, root_folder)
    file_name = os.path.basename(file_path)
    file_extension = os.path.splitext(file_name)[1]

    file_element = [
        f"    <file>\n        <name>{file_name}</name>\n        <path>{relative_path}</path>\n"
    ]

    if file_extension in FULL_CONTENT_EXTENSIONS:
        file_element.append("        <content>\n")
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                file_element.append(file.read())
        except UnicodeDecodeError:
            file_element.append("Binary or non-UTF-8 content not displayed")
        file_element.append("\n        </content>\n")
    else:
        file_element.append("        <content>Full content not provided</content>\n")

    file_element.append("    </file>\n")
    return "".join(file_element)

def get_repo_structure(root_folder):
    structure = ["<repository_structure>\n"]

    for subdir, dirs, files in os.walk(root_folder):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        level = subdir.replace(root_folder, "").count(os.sep)
        indent = " " * 4 * level
        relative_subdir = os.path.relpath(subdir, root_folder)

        structure.append(f'{indent}<directory name="{os.path.basename(subdir)}">\n')
        for file in files:
            file_path = os.path.join(subdir, file)
            file_element = create_file_element(file_path, root_folder)
            structure.append(file_element)
        structure.append(f"{indent}</directory>\n")

    structure.append("</repository_structure>\n")
    return "".join(structure)

def main():
    root_folder = os.getcwd()  # Use the current working directory
    base_dir = os.path.basename(root_folder)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(root_folder, f"{base_dir}_context_{timestamp}.txt")

    # Delete the previous output file if it exists
    for file in os.listdir(root_folder):
        if file.startswith(f"{base_dir}_context_") and file.endswith(".txt"):
            os.remove(os.path.join(root_folder, file))
            print(f"Deleted previous context file: {file}")

    repo_structure = get_repo_structure(root_folder)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Context extraction timestamp: {timestamp}\n\n")
        f.write(repo_structure)

    print(f"Fresh repository context has been extracted to {output_file}")

if __name__ == "__main__":
    main()