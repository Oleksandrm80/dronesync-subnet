with open('dashboard/app.py', 'r') as f:
    content = f.read()

fixes = [
    (
        '        from dronesync.replay_guard import ReplayGuard\n    _rg = ReplayGuard()\n    replay_panel = (',
        '        from dronesync.replay_guard import ReplayGuard\n        _rg = ReplayGuard()\n        replay_panel = ('
    ),
    (
        '        from validator.scorer import ValidatorIdentity\n    _vi = ValidatorIdentity',
        '        from validator.scorer import ValidatorIdentity\n        _vi = ValidatorIdentity'
    ),
    (
        '        from dronesync.swarm_consensus import SwarmConsensus, ByzantineDetector\n    _bc = SwarmConsensus',
        '        from dronesync.swarm_consensus import SwarmConsensus, ByzantineDetector\n        _bc = SwarmConsensus'
    ),
]

for old, new in fixes:
    if old in content:
        content = content.replace(old, new, 1)
        print('Fixed:', old[30:60])
    else:
        print('NOT FOUND:', old[30:60])

with open('dashboard/app.py', 'w') as f:
    f.write(content)
print('Done')
