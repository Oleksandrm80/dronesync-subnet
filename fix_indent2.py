with open('dashboard/app.py', 'r') as f:
    content = f.read()

old = '''    # Pipeline Panel
try:
    from dronesync.pipeline import MissionPipeline
pipeline_panel = (
        f'<div class="metric"><span class="mk">Status</span><span class="mv g">ACTIVE</span></div>'
        f'<div class="metric"><span class="mk">Steps</span><span class="mv c">10</span></div>'
        f'<div class="metric"><span class="mk">Signing</span><span class="mv g">Ed25519</span></div>'
        f'<div class="metric"><span class="mk">On-Chain</span><span class="mv g">READY</span></div>'
    )'''

new = '''    # Pipeline Panel
    try:
        from dronesync.pipeline import MissionPipeline
        pipeline_panel = (
            f\'<div class="metric"><span class="mk">Status</span><span class="mv g">ACTIVE</span></div>\'
            f\'<div class="metric"><span class="mk">Steps</span><span class="mv c">10</span></div>\'
            f\'<div class="metric"><span class="mk">Signing</span><span class="mv g">Ed25519</span></div>\'
            f\'<div class="metric"><span class="mk">On-Chain</span><span class="mv g">READY</span></div>\'
        )'''

if old in content:
    content = content.replace(old, new, 1)
    print('Fixed pipeline block')
else:
    print('NOT FOUND - checking...')
    idx = content.find('pipeline_panel = (')
    print('pipeline_panel at:', idx)
    print('Context:', repr(content[idx-50:idx+100]))

with open('dashboard/app.py', 'w') as f:
    f.write(content)
print('Done')
