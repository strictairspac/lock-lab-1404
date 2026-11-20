ROLES = ('admin', 'operator', 'viewer')
RUN_STATES = ('queued', 'running', 'completed', 'failed')
# 停写/封存单状态
FREEZE_STATES = ('freezing', 'sealed', 'released')
# 跨间移位状态
RELOCATION_STATES = ('moving', 'posted')
# 房间派生状态：normal 正常 / freezing 等待在途写完 / sealed 已封
ROOM_STATES = ('normal', 'freezing', 'sealed')
