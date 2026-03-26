import os

path = r'c:\Users\jason\Desktop\Dev Projects\collexions-2026\server.py'
with open(path, 'r') as f:
    lines = f.readlines()

output_lines = []
found = False
for line in lines:
    if 'app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)' in line:
        output_lines.append('    # Start core background service automatically\n')
        output_lines.append('    try:\n')
        output_lines.append('        start_background_process()\n')
        output_lines.append('        print("Auto-start core service: SUCCESS")\n')
        output_lines.append('    except Exception as e:\n')
        output_lines.append(f'        print(f"Auto-sync error: {{e}}")\n')
        output_lines.append('\n')
        output_lines.append(line)
        found = True
    else:
        output_lines.append(line)

if found:
    with open(path, 'w') as f:
        f.writelines(output_lines)
    print("SUCCESS")
else:
    print("NOT_FOUND")
