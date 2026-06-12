with open('dashboard/app.py', 'r') as f:
    content = f.read()

fixes = [
    # Pipeline except
    (
        'except Exception:\n    pipeline_panel',
        '    except Exception:\n        pipeline_panel'
    ),
    # Replay Guard
    (
        '# Replay Guard Panel\ntry:\n    from dronesync.replay_guard',
        '    # Replay Guard Panel\n    try:\n        from dronesync.replay_guard'
    ),
    (
        '        replay_panel = (\n            f\'<div class="metric"><span class="mk">Status</span><span class="mv g">ACTIVE</span></div>\'\n            f\'<div class="metric"><span class="mk">Protection</span>',
        '        replay_panel = (\n            f\'<div class="metric"><span class="mk">Status</span><span class="mv g">ACTIVE</span></div>\'\n            f\'<div class="metric"><span class="mk">Protection</span>'
    ),
    (
        'except Exception:\n    replay_panel',
        '    except Exception:\n        replay_panel'
    ),
    # Validator Identity
    (
        '# Validator Identity Panel\ntry:\n    from validator.scorer',
        '    # Validator Identity Panel\n    try:\n        from validator.scorer'
    ),
    (
        'except Exception:\n    validator_identity_panel',
        '    except Exception:\n        validator_identity_panel'
    ),
    # Byzantine
    (
        '# Byzantine Detector Panel\ntry:\n    from dronesync.swarm_consensus import SwarmConsensus, ByzantineDetector',
        '    # Byzantine Detector Panel\n    try:\n        from dronesync.swarm_consensus import SwarmConsensus, ByzantineDetector'
    ),
    (
        'except Exception:\n    byzantine_panel',
        '    except Exception:\n        byzantine_panel'
    ),
]

for old, new in fixes:
    if old in content:
        content = content.replace(old, new, 1)
        print('Fixed:', old[:40])
    else:
        print('NOT FOUND:', old[:40])

with open('dashboard/app.py', 'w') as f:
    f.write(content)
print('Done')

