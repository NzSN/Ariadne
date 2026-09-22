# AMD64 page-walk certificates

The page-walk component refines the effective `PageMap` abstraction from the
memory foundation. Its authoritative operators are in
[AMD64PageWalk.tla](../Specs/AMD64PageWalk.tla); the executable typed validator
and general proofs are in [PageWalk.lean](../lean/AMD64/PageWalk.lean).

The source baseline is AMD Volume 2 revision 3.45, July 2026. The primary
sections and one-based PDF pages are:

| Source ID | Section | PDF page |
| --- | --- | ---: |
| V2-SECTION-0442 | 5.2 Legacy-Mode Page Translation | 195 |
| V2-SECTION-0444 | 5.2.2 Normal Non-PAE Paging | 196 |
| V2-SECTION-0445 | 5.2.3 PAE Paging | 199 |
| V2-SECTION-0446 | 5.3 Long-Mode Page Translation | 203 |
| V2-SECTION-0448 | 5.3.2 CR3 | 204 |
| V2-SECTION-0449 | 5.3.3 4-Kbyte Page Translation | 205 |
| V2-SECTION-0450 | 5.3.4 2-Mbyte Page Translation | 209 |
| V2-SECTION-0451 | 5.3.5 1-Gbyte Page Translation | 213 |
| V2-SECTION-0452 | 5.4 Page-Translation-Table Entry Fields | 217 |
| V2-SECTION-0454 | 5.4.2 Notes on Accessed and Dirty Bits | 221 |
| V2-SECTION-0459 | 5.6 Page-Protection Checks | 225 |
| V2-SECTION-0471 | 5.8 Protection Across Paging Hierarchy | 231 |

## Certificate contract

A certificate contains the raw entries fetched during a walk. Each entry keeps
its level, the physical address from which it was fetched, and all 64 raw bits.
The page-table memory evidence also carries the four or eight little-endian
bytes and an availability flag. Validation reconstructs the raw word from those
bytes. An unavailable captured word makes the certificate incomplete; it does
not create a not-present page or #PF.
TLA+ also carries a 65-bit addition certificate for every physical entry
address. The validator checks this chain:

```text
configured CR3-derived root
  + scaled index from the full-width linear address
  = physical address of first raw entry

base field of entry N
  + scaled index for level N+1
  = physical address of entry N+1
```

The raw entry and its bytes must exist in the explicit physical page-table memory supplied to
the validator. No callback chooses an entry or translation. An invalid or
incomplete certificate is a tool-input error, distinct from an architectural
page fault.

Long-mode and PAE entries are eight bytes, so the selected index is shifted by
three. Non-PAE legacy entries are four bytes, so the index is shifted by two.
The full architectural 64-bit address maps are retained. The fixture happens
to use zero indices and self-referential zero-based tables to keep TLC finite;
that does not reduce the semantic address width.

## Implemented path shapes

| Variant | 4 KiB | Large leaves | Executable evidence | Coverage status |
| --- | --- | --- | --- | --- |
| Four-level long mode | PML4, PDPT, PD, PT | 2 MiB PD; 1 GiB PDPT | Positive, not-present, NX-reserved, permission-combination and A/D fixtures | Common walk complete; variant-exhaustive reserved bits open |
| Five-level long mode | PML5, PML4, PDPT, PD, PT | 2 MiB PD; 1 GiB PDPT | Positive 4 KiB fixture and shared validators | LA57 enable/transition and exhaustive reserved bits open |
| Legacy PAE | Four-entry PDPT, PD, PT | 2 MiB PD | Positive 4 KiB fixture; PDPT NX suppression implemented | CR3/PDPT loading and older-processor reserved-fault timing open |
| Legacy non-PAE | PD, PT | 4 MiB PD | Positive 4 KiB and 4 MiB fixtures | PSE/PSE36 address encoding and exact 32-bit entry matrix open |

The status column matters. Supporting a path shape and common entry fields does
not close all behavior for that paging variant.

## Raw entry and reserved-bit rules

The component reads P, R/W, U/S, A, D, PS, address, protection-key, and NX
directly from the raw word. It rejects these common reserved conditions:

- NX set while EFER.NXE is clear where that level defines NX;
- address bits above the implemented physical-address width;
- PS at an intermediate level that cannot be a leaf;
- missing PS at a 2 MiB, 1 GiB, or legacy 4 MiB leaf;
- PS at a 4 KiB PTE;
- non-zero physical-base bits below a large page's required alignment;
- a 1 GiB leaf when the profile does not support it;
- high bits in the 64-bit carrier used to represent a 32-bit non-PAE entry.

Some bits change meaning by level, page size, extension, and processor
generation. PAT, global-page, available-to-software fields, PSE36, PCID, CR3
PWT/PCD, and every old PAE PDPT reserved-bit timing rule still need explicit
variant matrices. Until those matrices and negative fixtures exist, M3 is not
complete.

## Derived translation and protection

A successful certificate produces an effective `PageMapping`:

- the page base comes from the final entry and is aligned to 4 KiB, 2 MiB,
  1 GiB, or legacy 4 MiB as selected by the path;
- effective R/W is true only when every traversed entry has R/W set;
- effective U/S is true only when every traversed entry has U/S set;
- effective NX is true when any level whose variant defines NX has NX set;
- the protection key comes from the leaf entry;
- the linear tag retains all bits above the page offset.

Legacy PAE PDPTEs do not contribute R/W, U/S, NX, A, or D. Their corresponding
reserved bits must be zero; permission combination and A-update events start at
the PDE. A dedicated PAE fixture keeps those PDPTE bits zero while deriving a
writable user mapping from the PDE and PTE.

The mapping's memory type is explicitly unresolved. PWT, PCD, PAT, MTRRs, and
the system's fixed/variable type configuration must be combined before D1 can
attach a concrete memory type; successful translation does not default to WB.

The memory foundation then applies CPL, CR0.WP, SMEP, SMAP, RFLAGS.AC, PKRU,
and shadow-stack checks. A walk certificate proves how the mapping was derived;
it does not bypass the later access-permission step.

A not-present walk fault reports P=0 while retaining the access's W/R and U/S
facts. I/D is defined only with NXE and PAE enabled; SS is defined only with CET
enabled, and the fault record carries those definedness facts explicitly. A
reserved-bit walk fault reports P=1 and RSVD=1. Both identify the
failed level and physical entry address. CR2 remains the original failed linear
address and is attached by the exception layer.

## Accessed and Dirty effects

The A/D contract follows Volume 2 section 5.4.2:

- The processor never sets A or D in a not-present entry.
- A can be set speculatively and is not ordered against loads from other
  instructions.
- A set-bit requests for a valid prefix can remain visible when a later entry causes a
  not-present or reserved-bit fault.
- D is not speculative. The translation outcome itself emits only A requests.
  `successfulADUpdates` emits a leaf D request only after its caller has
  established an architecturally allowed write.
- Instructions with several writes can leave D set for writes completed before
  a later fault. Rare instruction-specific cases may set D without a performed
  data write; those forms must opt into that behavior and remain inventoried.

Updates are explicit set-bit requests: false never requests clearing a
preexisting A or D bit. They carry the walk position as well as the physical entry address. This
preserves multiple level effects even for recursive page tables in which two
levels can refer to the same physical entry. Applying the events merges A/D bits
in physical memory; the event list itself remains ordered evidence.

The current model does not simulate a TLB hit. A TLB hit can translate without
reading the tables or producing new A/D writes. TLB state, invalidation, PCID,
global mappings, and speculative interleavings remain separate obligations.

## Proof and validation boundary

Lean proves the fixed hierarchy depths, scaled-index low-bit behavior, table
base alignment, Boolean address reflexivity, absence of Dirty writes on a read
walk, and raw-field correspondence with the reviewed TLA+ transcription.
Neither language parses the other. Source hashes, operator review, and shared
fixtures guard this trust boundary.

The TLA+ fixture covers all four path families, the three long-mode page sizes,
the legacy 4 MiB path, permission combination, not-present access bits,
NX-with-NXE-clear reserved faults, valid-prefix A updates, and successful leaf
D updates. These checks establish the named operators over the fixture state
graph; they do not claim hardware differential conformance. The current host is
Intel under Hyper-V and cannot supply AMD-native evidence.
