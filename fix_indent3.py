with open('dashboard/app.py', 'r') as f:
    content = f.read()

old = 'rom dronesync.pipeline import MissionPipeline\n    pipeline_panel = ('
new = 'rom dronesync.pipeline import MissionPipeline\n        pipeline_panel = ('

if old in content:
    content = content.replace(old, new, 1)
    print('Fixed')
else:
    print('NOT FOUND')

with open('dashboard/app.py', 'w') as f:
    f.write(content)
print('Done')
