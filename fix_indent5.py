with open('dashboard/app.py', 'r') as f:
    content = f.read()

fixes = [
    (
        '        _vi = ValidatorIdentity("VALIDATOR_001")\n    validator_identity_panel = (',
        '        _vi = ValidatorIdentity("VALIDATOR_001")\n        validator_identity_panel = ('
    ),
    (
        '        _bc = SwarmConsensus(["D1", "D2", "D3"])\n    _bd = ByzantineDetector',
        '        _bc = SwarmConsensus(["D1", "D2", "D3"])\n        _bd = ByzantineDetector'
    ),
    (
        '        _bds = _bd.get_status()\n    byzantine_panel = (',
        '        _bds = _bd.get_status()\n        byzantine_panel = ('
    ),
    (
        '        _rg = ReplayGuard()\n        replay_panel = (',
        '        _rg = ReplayGuard()\n        replay_panel = ('
    ),
]

for old, new in fixes:
    if old in content:
        content = content.replace(old, new, 1)
        print('Fixed:', old[20:50])
    else:
        print('NOT FOUND:', old[20:50])

with open('dashboard/app.py', 'w') as f:
    f.write(content)
print('Done')
