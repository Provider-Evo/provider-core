import os

directories = ["src/core", "src/routes", "src/platforms", "src/webui", "tests"]
root_files = ["main.py"]
all_files = []

for directory in directories:
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                all_files.append(os.path.join(root, file))

for file in root_files:
    if os.path.exists(file):
        all_files.append(file)

all_files.sort()

for filepath in all_files:
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = sum(1 for _ in f)
    except:
        lines = 0
    
    basename = os.path.basename(filepath)
    dirname = os.path.dirname(filepath).replace("\\", "/")
    
    if "test_" in basename or basename == "conftest.py":
        file_type = "Test"
    elif basename in ["main.py", "app.py", "server.py"]:
        file_type = "Main Module"
    elif "util" in basename.lower():
        file_type = "Utility"
    elif basename == "__init__.py":
        file_type = "Module (init)"
    elif "test_" in dirname:
        file_type = "Test"
    else:
        file_type = "Module"
    
    print(f"{filepath}|{lines}|{file_type}")
