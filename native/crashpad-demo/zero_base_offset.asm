; Controlled I5b positive and indexed admission-negative instructions.
; Caller supplies zero operands; actual exception context remains the evidence.
PUBLIC AriadneCrashDemoZeroBaseOffset
PUBLIC AriadneCrashDemoZeroBaseOffsetIndexed
.code
AriadneCrashDemoZeroBaseOffset PROC
    mov dword ptr [rcx + 8], 5
    ret
AriadneCrashDemoZeroBaseOffset ENDP
AriadneCrashDemoZeroBaseOffsetIndexed PROC
    mov dword ptr [rcx + rdx + 8], 5
    ret
AriadneCrashDemoZeroBaseOffsetIndexed ENDP
END
