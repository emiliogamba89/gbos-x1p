#!/usr/bin/env python3
# Sostituisce 'no-map;' con 'nomap-off;' nel dts: le regioni reserved-memory
# restano riservate (memblock_reserve) MA vengono mappate nella linear map,
# cosi' il kernel GKI caricato da GRUB/EFI-stub non puo' sovrapporsi a una
# regione saltata (crash silenzioso pre-printk su hardware ThinkBook).
import sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()
n = s.count('no-map;')
s = s.replace('no-map;', 'nomap-off;')
open(dst, 'w').write(s)
print(f'nomap-off: {n} regioni convertite')
