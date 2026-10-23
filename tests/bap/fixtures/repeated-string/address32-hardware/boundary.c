/*
 * Optional Linux x86-64 hardware observation fixture for one element spanning
 * the 4 GiB linear-address boundary. Requires MAP_FIXED_NOREPLACE and permission
 * to map 0xfffff000..0x100000fff; exit 2 means this prerequisite was unavailable.
 * Build and run from the repository root:
 *
 *   mkdir -p target/rep-address-hardware
 *   cc -O0 tests/bap/fixtures/repeated-string/address32-hardware/boundary.c -o target/rep-address-hardware/boundary
 *   LC_ALL=C lscpu > target/rep-address-hardware/cpu.txt
 *   timeout 30 target/rep-address-hardware/boundary > target/rep-address-hardware/boundary.txt
 *
 * Exact instruction 67 F3 48 AD, low count 1, RSI=0x12345678fffffffc.
 * The starting effective address truncates to 0xfffffffc; the eight-byte load
 * remains contiguous across 4 GiB, then ESI advances modulo 2^32. Corroborating
 * output has RCX=0, RSI=4, RAX=0x131211100f0e0d0c. Both the tested Ryzen 7950X
 * and Intel Core 5 220H produced this result. Record CPU identity with any run.
 *
 * This fixture emits observations and earns no portable unit-test acceptance.
 * It does not exercise noncanonical addresses, faults, restart, or 64-bit wrap.
 * The executable body is preserved from the original qualification probe.
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
int main(void){
unsigned char *p=mmap((void*)0xfffff000ULL,8192,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
if(p==MAP_FAILED){perror("mmap");return 2;}
for(int i=0;i<8192;i++)p[i]=(unsigned char)(i+0x10);
uint64_t c=1,s=0x12345678fffffffcULL,a=0xdeadbeef12345678ULL;
__asm__ volatile("cld; .byte 0x67,0xf3,0x48,0xad" : "+c"(c),"+S"(s),"+a"(a) : : "memory","cc");
printf("RCX=%016lx RSI=%016lx RAX=%016lx expected=%016lx\n",c,s,a,*(uint64_t*)(p+4092));
munmap(p,8192);return 0;}
