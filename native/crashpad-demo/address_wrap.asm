; Four new I5c recipes. Windows x64 caller supplies RCX and RDX explicitly.
; Each public entry is the faulting MOV followed immediately by RET.
; These instructions do not initialize operands or manufacture observations.
PUBLIC AriadneCrashDemoAddressWrapUpper
PUBLIC AriadneCrashDemoAddressWrapNoWrap
PUBLIC AriadneCrashDemoAddressWrapNegative
PUBLIC AriadneCrashDemoAddressWrapIndexed
.code
AriadneCrashDemoAddressWrapUpper PROC
    mov dword ptr [rcx + 16], 5
    ret
AriadneCrashDemoAddressWrapUpper ENDP
AriadneCrashDemoAddressWrapNoWrap PROC
    mov dword ptr [rcx], 5
    ret
AriadneCrashDemoAddressWrapNoWrap ENDP
AriadneCrashDemoAddressWrapNegative PROC
    mov dword ptr [rcx - 8], 5
    ret
AriadneCrashDemoAddressWrapNegative ENDP
AriadneCrashDemoAddressWrapIndexed PROC
    mov dword ptr [rcx + rdx + 16], 5
    ret
AriadneCrashDemoAddressWrapIndexed ENDP
END
