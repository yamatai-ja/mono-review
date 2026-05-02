import os
import re

src_dir = 'src'
wrapper_file = 'src/layouts/helpers/ReactIconsWrapper.tsx'
icons_to_export = {}  # module -> set of icons

# 1. Find all react-icons imports
for root, dirs, files in os.walk(src_dir):
    for file in files:
        if file.endswith('.astro'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            matches = list(re.finditer(r'import\s+{\s*([^}]+)\s*}\s+from\s+["\']react-icons/([^"\']+)["\'];?', content))
            if not matches:
                continue
            
            modified = False
            for match in matches:
                icons_str = match.group(1)
                module = match.group(2)
                icons = [i.strip() for i in icons_str.split(',')]
                
                if module not in icons_to_export:
                    icons_to_export[module] = set()
                icons_to_export[module].update(icons)
                
                # Replace the import
                new_import = f'import {{ {", ".join(icons)} }} from "@/layouts/helpers/ReactIconsWrapper";'
                content = content.replace(match.group(0), new_import)
                modified = True
            
            if modified:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Updated imports in {filepath}")

# 2. Create the wrapper file
wrapper_content = "import React from 'react';\n"
for module, icons in icons_to_export.items():
    wrapper_content += f'import {{ {", ".join([f"{i} as _{i}" for i in sorted(icons)])} }} from "react-icons/{module}";\n'

wrapper_content += "\n"

for module, icons in icons_to_export.items():
    for i in sorted(icons):
        wrapper_content += f'export const {i} = (props: any) => <_{i} {{...props}} />;\n'

with open(wrapper_file, 'w', encoding='utf-8') as f:
    f.write(wrapper_content)

print(f"Created wrapper at {wrapper_file}")
