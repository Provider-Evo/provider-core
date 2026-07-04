import pathlib
content_path = pathlib.Path(r"X:/Project/provider-self/.agents/tmp/plan_content.txt")
dest = pathlib.Path(r"C:/Users/SuperAdmin/.codebuddy/plans/radiant-forging-turing.md")
dest.parent.mkdir(parents=True, exist_ok=True)
import shutil
shutil.copy2(content_path, dest)
print(f"Copied {dest.stat().st_size} bytes")