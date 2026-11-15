#!/usr/bin/env python3
"""Patch v3 di services.jar (androguard per le istruzioni):
 1. Watchdog.run(): NOP delle invoke-static a Process.killProcess / System.exit /
    Runtime.halt (il Watchdog non puo' piu' uccidere system_server sotto TCG).
 2. Watchdog.breakCrashLoop(): corpo -> return-void (evita il doSysRq('c') che
    farebbe panicare il kernel dopo i restart in loop).
 3. ExternalCaptureStateTracker.run(): corpo -> return-void (polla AudioSystem;
    con HAL audio rotto un assert nativo 'status != NO_ERROR' aborta
    system_server: la run non polla piu').
Aggiorna adler32+sha1 del dex header e ricompone lo zip.
Uso: patch_services_v3.py <services.jar-in> <services.jar-out>
"""
import sys
import zipfile

from androguard.core.bytecodes.dvm import DalvikVMFormat
from dex_checksums import finalize_dex, write_aligned_jar

NOP = b"\x00\x00"
RETURN_VOID = b"\x0e\x00"
KILL_STRINGS = ("Landroid/os/Process;->killProcess",
                "Ljava/lang/System;->exit",
                "Ljava/lang/Runtime;->halt")


def code_info(method):
    code = method.get_code()
    return code.get_off() + 16, code.get_insns_size()


def patch_watchdog_run(data, method):
    insns_off, insns_size = code_info(method)
    nopped = 0
    off = insns_off
    for inst in method.get_code().get_bc().get_instructions():
        op = inst.get_op_value()
        length = inst.get_length()
        if op in (0x71, 0x77):  # invoke-static / range
            try:
                ops = inst.get_operands()
            except Exception:
                ops = []
            if ops:
                last = ops[-1]
                if len(last) >= 3 and isinstance(last[2], str):
                    if any(k in last[2] for k in KILL_STRINGS):
                        data[off:off + 6] = NOP * 3
                        nopped += 1
                        print(f"[nop] Watchdog.run @insns+{off - insns_off}: {last[2]}")
        off += length
    return nopped


def neutralize(data, method):
    insns_off, insns_size = code_info(method)
    data[insns_off:insns_off + insns_size * 2] = RETURN_VOID + NOP * (insns_size - 1)
    print(f"[ok] {method.get_name()} -> return-void ({insns_size} unita')")


def main(src, dst):
    zin = zipfile.ZipFile(src)
    out = {}
    done_run = done_break = done_tracker = False
    for n in zin.namelist():
        b = bytearray(zin.read(n))
        if n.endswith(".dex") and not (done_run and done_break and done_tracker):
            dvm = DalvikVMFormat(bytes(b))
            for c in dvm.get_classes():
                cname = c.get_name()
                if cname == "Lcom/android/server/Watchdog;":
                    for m in c.get_methods():
                        if m.get_name() == "run" and not done_run:
                            nopped = patch_watchdog_run(b, m)
                            assert nopped >= 2, f"attese >=2 kill noppate, trovate {nopped}"
                            done_run = True
                        elif m.get_name() == "breakCrashLoop" and not done_break:
                            neutralize(b, m)
                            done_break = True
                elif (cname == "Lcom/android/server/soundtrigger_middleware/"
                      "ExternalCaptureStateTracker;") and not done_tracker:
                    for m in c.get_methods():
                        if m.get_name() == "run":
                            neutralize(b, m)
                            done_tracker = True
            if done_run or done_break or done_tracker:
                b = bytearray(finalize_dex(b))
                print(f"[sha] {n}: checksum aggiornati")
        out[n] = b
    assert done_run and done_break and done_tracker, \
        f"patch incomplete: run={done_run} break={done_break} tracker={done_tracker}"
    write_aligned_jar(dst, out)
    print("OK ->", dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
