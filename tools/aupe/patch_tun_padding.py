#!/usr/bin/env python3
"""Fix stale S4 padding cached while RoutineReadFromTUN blocks in tun.Read."""
from pathlib import Path
import sys
p=Path(sys.argv[1] if len(sys.argv)>1 else 'device/send.go')
s=p.read_text()
old='''\t\t// read packets
\t\tcount, readErr = device.tun.device.Read(bufs, sizes, offset)
\t\tfor i := 0; i < count; i++ {
'''
new='''\t\t// read packets
\t\tcount, readErr = device.tun.device.Read(bufs, sizes, offset)
\t\t// S4 can change while Read blocks. Packet bytes used the old offset.
\t\tcurrentPadding := device.paddings.transport.Load()
\t\tif currentPadding != padding {
\t\t\tnewOffset := MessageTransportHeaderSize + int(currentPadding)
\t\t\tfor i := 0; i < count; i++ {
\t\t\t\tif sizes[i] < 1 { continue }
\t\t\t\tif newOffset+sizes[i] > len(bufs[i]) {
\t\t\t\t\t// Never submit a truncated or misframed packet.
\t\t\t\t\tsizes[i] = 0
\t\t\t\t\tcontinue
\t\t\t\t}
\t\t\t\tcopy(bufs[i][newOffset:newOffset+sizes[i]], bufs[i][offset:offset+sizes[i]])
\t\t\t}
\t\t\tpadding = currentPadding
\t\t\toffset = newOffset
\t\t}
\t\tfor i := 0; i < count; i++ {
'''
if s.count(old)!=1: raise SystemExit(f'expected exactly one source match, found {s.count(old)}')
p.write_text(s.replace(old,new,1))
print('patched',p)
