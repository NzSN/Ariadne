; Copyright 2026 The Crashpad Authors
;
; Licensed under the Apache License, Version 2.0 (the "License");
; you may not use this file except in compliance with the License.
; You may obtain a copy of the License at
;
;     http://www.apache.org/licenses/LICENSE-2.0
;
; Unless required by applicable law or agreed to in writing, software
; distributed under the License is distributed on an "AS IS" BASIS,
; WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
; See the License for the specific language governing permissions and
; limitations under the License.
;
; Controlled Windows x64 leaf: 98 decoded starts, no internal alignment.
; RCX points to eight immutable u64 inputs; RDX holds the independent checksum.
; Only volatile registers and the caller-provided home slots are modified.
; RSP remains unchanged. Every unrolled round feeds the final null address.

.code
PUBLIC AriadneCrashDemoBapWorkload
PUBLIC AriadneCrashDemoBapWorkloadProducer
PUBLIC AriadneCrashDemoBapWorkloadFault
PUBLIC AriadneCrashDemoBapWorkloadEnd

AriadneCrashDemoBapWorkload PROC
    mov r10, rcx
    mov r11, rdx
    mov rax, [r10]
    mov r9d, 0

    ; Unrolled round 0: nine instructions.
    mov r8, [r10]
    add rax, r8
    not rax
    lea rax, [rax+1]
    mov [rsp+8], rax
    mov r8, [rsp+8]
    lea rax, [r8+r8*2]
    add rax, r8
    lea rax, [rax+3]

    ; Unrolled round 1: nine instructions.
    mov r8, [r10+8]
    add rax, r8
    not rax
    lea rax, [rax+2]
    mov [rsp+8], rax
    mov r8, [rsp+8]
    lea rax, [r8+r8*2+1]
    add rax, r8
    lea rax, [rax+4]

    ; Unrolled round 2: nine instructions.
    mov r8, [r10+16]
    add rax, r8
    not rax
    lea rax, [rax+3]
    mov [rsp+8], rax
    mov r8, [rsp+8]
    lea rax, [r8+r8*2+2]
    add rax, r8
    lea rax, [rax+5]

    ; Unrolled round 3: nine instructions.
    mov r8, [r10+24]
    add rax, r8
    not rax
    lea rax, [rax+4]
    mov [rsp+8], rax
    mov r8, [rsp+8]
    lea rax, [r8+r8*2+3]
    add rax, r8
    lea rax, [rax+6]

    ; Unrolled round 4: nine instructions.
    mov r8, [r10+32]
    add rax, r8
    not rax
    lea rax, [rax+5]
    mov [rsp+8], rax
    mov r8, [rsp+8]
    lea rax, [r8+r8*2+4]
    add rax, r8
    lea rax, [rax+7]

    ; Unrolled round 5: nine instructions.
    mov r8, [r10+40]
    add rax, r8
    not rax
    lea rax, [rax+6]
    mov [rsp+8], rax
    mov r8, [rsp+8]
    lea rax, [r8+r8*2+5]
    add rax, r8
    lea rax, [rax+8]

    ; Unrolled round 6: nine instructions.
    mov r8, [r10+48]
    add rax, r8
    not rax
    lea rax, [rax+7]
    mov [rsp+8], rax
    mov r8, [rsp+8]
    lea rax, [r8+r8*2+6]
    add rax, r8
    lea rax, [rax+9]

    ; Unrolled round 7: nine instructions.
    mov r8, [r10+56]
    add rax, r8
    not rax
    lea rax, [rax+8]
    mov [rsp+8], rax
    mov r8, [rsp+8]
    lea rax, [r8+r8*2+7]
    add rax, r8
    lea rax, [rax+10]

AriadneBapWorkloadLoad:
    mov r8, [r10+r9*8]
    add rax, r8
    inc r9
    mov r8d, 4
    cmp r9, r8
    jne SHORT AriadneBapWorkloadLoad

    mov r8d, 1
    test rax, r8
    jne SHORT AriadneBapWorkloadOdd
    lea rax, [rax+7]
    jmp SHORT AriadneBapWorkloadJoin
AriadneBapWorkloadOdd:
    lea rax, [rax+11]

AriadneBapWorkloadJoin:
    mov [rsp+16], rax
    mov r8, [rsp+16]
    lea r8, [r8+17]
    not r8
    inc r8
    add r8, r11
    mov rax, r8
AriadneCrashDemoBapWorkloadProducer:
    mov rcx, rax
AriadneCrashDemoBapWorkloadFault:
    mov dword ptr [rcx], 5
    ret
AriadneCrashDemoBapWorkloadEnd:
AriadneCrashDemoBapWorkload ENDP
END
