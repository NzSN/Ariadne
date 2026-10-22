param([Parameter(Mandatory=$true)][string]$Dump)
$ErrorActionPreference = 'Stop'
if (-not [Environment]::Is64BitProcess) { throw 'A 64-bit Windows process is required' }
# An independent operating-system reference, run only on positive synthetic
# captures. It never executes captured code or registers an exception handler.
Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class AriadneUnwindReference {
    [StructLayout(LayoutKind.Sequential)]
    public struct RuntimeFunction { public uint Begin, End, Unwind; }
    [DllImport("ntdll.dll")]
    static extern IntPtr RtlVirtualUnwind(uint type, ulong image, ulong pc,
        ref RuntimeFunction function, IntPtr context, out IntPtr handler,
        out ulong establisher, IntPtr pointers);
    public sealed class Observation {
        public ulong pc, sp;
        public Dictionary<string, ulong> registers = new Dictionary<string, ulong>();
        public string reference = "Windows RtlVirtualUnwind";
        public string windows = Environment.OSVersion.Version.ToString();
    }
    static uint U32(byte[] b, int n) { return BitConverter.ToUInt32(b, n); }
    static ulong U64(byte[] b, int n) { return BitConverter.ToUInt64(b, n); }
    static void Put(byte[] b, int n, ulong x) { Array.Copy(BitConverter.GetBytes(x), 0, b, n, 8); }
    static int Stream(byte[] b, uint kind) {
        int directory = checked((int)U32(b, 12));
        for (int i = 0; i < U32(b, 8); ++i) {
            int at = checked(directory + 12*i);
            if (U32(b, at) == kind) return checked((int)U32(b, at+8));
        }
        throw new InvalidDataException("missing synthetic minidump stream");
    }
    static ulong Relocate(ulong value, ulong from, ulong to, uint size) {
        return value >= from && value - from < size ? to + (value - from) : value;
    }
    static byte[] Span(byte[] b, int at, int size) {
        byte[] result = new byte[size]; Array.Copy(b, at, result, 0, size); return result;
    }
    public static Observation Run(string path) {
        byte[] dump = File.ReadAllBytes(path);
        int modules = Stream(dump, 4), memory = Stream(dump, 5), threads = Stream(dump, 3);
        int exception = Stream(dump, 6);
        if (U32(dump, modules) != 1 || U32(dump, threads) != 1)
            throw new InvalidDataException("reference accepts one-module one-thread synthetic captures only");
        ulong imageVA = U64(dump, modules+4), stackVA = U64(dump, threads+4+24);
        uint imageSize = U32(dump, modules+12), stackSize = U32(dump, threads+4+32);
        if (imageSize > 1048576 || stackSize > 1048576 || stackSize < 8)
            throw new InvalidDataException("synthetic reference allocation bound");
        byte[] imageBytes = null;
        for (int i = 0; i < U32(dump, memory); ++i) {
            int at = checked(memory+4+16*i);
            if (U64(dump, at) == imageVA && U32(dump, at+8) == imageSize)
                imageBytes = Span(dump, checked((int)U32(dump, at+12)), checked((int)imageSize));
        }
        if (imageBytes == null) throw new InvalidDataException("missing complete synthetic image capture");
        byte[] stackBytes = Span(dump, checked((int)U32(dump, threads+4+36)), checked((int)stackSize));
        int contextSize = checked((int)U32(dump, exception+160));
        if (contextSize != 1232) throw new InvalidDataException("expected AMD64 CONTEXT");
        byte[] contextBytes = Span(dump, checked((int)U32(dump, exception+164)), contextSize);
        IntPtr image = Marshal.AllocHGlobal(checked((int)imageSize));
        IntPtr stackRaw = Marshal.AllocHGlobal(checked((int)stackSize+16));
        IntPtr contextRaw = Marshal.AllocHGlobal(contextSize+16);
        IntPtr stack = new IntPtr((stackRaw.ToInt64()+15)&~15L);
        IntPtr context = new IntPtr((contextRaw.ToInt64()+15)&~15L);
        try {
            ulong imageHost = unchecked((ulong)image.ToInt64()), stackHost = unchecked((ulong)stack.ToInt64());
            Func<ulong, ulong> relocate = value => Relocate(Relocate(value, imageVA, imageHost, imageSize), stackVA, stackHost, stackSize);
            Func<ulong, ulong> normalize = value => Relocate(Relocate(value, imageHost, imageVA, imageSize), stackHost, stackVA, stackSize+1);
            // Synthetic saved pointers are aligned words. This is not a general
            // minidump relocator and is never used by the production reader.
            for (int at=0; at+8<=stackBytes.Length; at+=8) Put(stackBytes, at, relocate(U64(stackBytes, at)));
            for (int at=120; at<=248; at+=8) Put(contextBytes, at, relocate(U64(contextBytes, at)));
            Marshal.Copy(imageBytes, 0, image, imageBytes.Length);
            Marshal.Copy(stackBytes, 0, stack, stackBytes.Length);
            Marshal.Copy(contextBytes, 0, context, contextBytes.Length);
            int pe = checked((int)U32(imageBytes, 60));
            int optional = pe+24;
            uint table = U32(imageBytes, optional+112+3*8), tableSize=U32(imageBytes, optional+112+3*8+4);
            ulong originalPc = U64(dump, checked((int)U32(dump, exception+164))+248);
            uint pcRva = checked((uint)(originalPc-imageVA));
            RuntimeFunction function = new RuntimeFunction(); bool found=false;
            for (uint at=table; at<table+tableSize; at+=12) {
                uint begin=U32(imageBytes, checked((int)at)), end=U32(imageBytes, checked((int)at+4));
                if (pcRva >= begin && pcRva < end) {
                    function.Begin=begin; function.End=end; function.Unwind=U32(imageBytes, checked((int)at+8)); found=true; break;
                }
            }
            if (!found) throw new InvalidDataException("no synthetic runtime function for captured PC");
            IntPtr handler; ulong establisher;
            RtlVirtualUnwind(0, imageHost, imageHost+pcRva, ref function, context, out handler, out establisher, IntPtr.Zero);
            Marshal.Copy(context, contextBytes, 0, contextBytes.Length);
            Observation result=new Observation(); result.pc=normalize(U64(contextBytes,248)); result.sp=normalize(U64(contextBytes,152));
            string[] banks={"rax","rcx","rdx","rbx","rsp","rbp","rsi","rdi","r8","r9","r10","r11","r12","r13","r14","r15"};
            for(int i=0;i<banks.Length;++i) result.registers[banks[i]]=normalize(U64(contextBytes,120+i*8));
            result.registers["rip"]=result.pc;
            return result;
        } finally { Marshal.FreeHGlobal(contextRaw); Marshal.FreeHGlobal(stackRaw); Marshal.FreeHGlobal(image); }
    }
}
'@
[AriadneUnwindReference]::Run($Dump) | ConvertTo-Json -Compress -Depth 5
