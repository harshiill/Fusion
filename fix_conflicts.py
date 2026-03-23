import os
import re

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if '<<<<<<< HEAD' not in content:
        return False
        
    # We will replace the conflict block with the HEAD block (the refactored code)
    pattern = re.compile(r'<<<<<<< HEAD\n(.*?)\n=======\n.*?\n>>>>>>> [^\n]+', re.DOTALL)
    
    new_content = pattern.sub(r'\1', content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    return True

for root, dirs, files in os.walk('FusionIIIT/applications/health_center'):
    for file in files:
        if file.endswith('.py'):
            fp = os.path.join(root, file)
            if fix_file(fp):
                print(f"Fixed {fp}")
