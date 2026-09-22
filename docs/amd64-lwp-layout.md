# AMD64 Lightweight Profiling control-block layout

The paired layout model is in `Specs/AMD64LWPLayout.tla` and
`lean/AMD64/LWPLayout.lean`. Its authority is AMD APM Volume 2 revision 3.45:
LWP capability enumeration on PDF pages 535-539 and the LWPCB layout and fields
on pages 545-554.

The processor profile supplies `LwpCbSize`, `LwpEventSize`, `LwpMaxEvents`,
`LwpEventOffset`, `LwpMinBufferSize`, available flags, and per-event minimum
intervals. A valid layout requires a nonzero event size, an eight-byte aligned
event offset at or beyond byte 88, at least one event, and enough control-block
bytes for all interval/counter pairs.

The fixed fields are decoded little-endian at their architectural byte offsets:
Flags 0, BufferSize/Random 4, BufferBase 8, BufferHeadOffset 16,
MissedEvents 24, Threshold 32, Filters 36, BaseIP 40, LimitIP 48, and
BufferTailOffset 64. Event interval/counter pairs begin at `LwpEventOffset`,
occupy eight bytes per EventId, and use signed low-26-bit values.

Normalization masks requested flags by available processor/OS features, rounds
buffer size, head, and threshold down to event-size multiples, maps an oversized
head to zero, maps negative counters to zero, and applies implementation minimum
intervals except that EventId 1 permits zero. Tail alignment and reserved fields
are reported as protocol obligations. They are not converted into #GP because
the cited text does not specify those faults.

Architectural decoding reads bytes from total `ConcreteMemory.Store` through
`decodeConcrete`. Captured `MemoryState` is handled only by `decodeCaptured`.
An absent captured byte yields `unavailable`, and
`captured_bytes_match_concrete` proves that complete captured evidence agrees
with the architectural concrete byte sequence under the existing refinement
relation.

This module does not execute LLWPCB or write ring records. Those later layers
must resolve concrete spans, preserve ordered partial effects, and apply the
Volume 2 page-fault policy without replacing machine state through an
environment callback.
