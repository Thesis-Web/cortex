#!/usr/bin/env python3
# g35/page_patch6b.py (2026-11-02, 15:30): the seeding of a point's drawing from the brain's place is taken out again. The brain's places after
# ten passes of 0.04 a step sit within a cube of some thirty units, while the page's rest lengths are 10 to 64 and its space-apart grid 15:
# twenty thousand points seeded into a few grid cells made the space-apart pass quadratic and the page's thread never answered (probe: no
# answer in 300 s; the unpatched page was ready in 57 s). The page draws as before; the brain's place is read on click and the sliders start
# from the brain's formula rows (page_patch6.py's other changes stay).
import sys
for p in sys.argv[1:]:
    s = open(p, encoding='utf-8').read()
    old = "      var bx = (!fixed && !n.ghost && !n.mem) ? XYZ[+k] : null; if (bx) { n.pos.set(bx[1], bx[2], bx[3]); n.unplaced = false; }   // the brain's own place for the point, when it holds one: the drawing starts there\n"
    assert s.count(old) == 1, (p, s.count(old)); s = s.replace(old, ""); open(p, 'w', encoding='utf-8').write(s); print('patched', p)
