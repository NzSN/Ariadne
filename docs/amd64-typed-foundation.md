# Typed AMD64 register-view foundation

This is the checked starting point for the
[accepted full AMD64 design](amd64-semantics-design.md). It uses Markdown and
typed pseudocode; the actual checked definitions are in
[`lean/AMD64/RegisterViews.lean`](../lean/AMD64/RegisterViews.lean).

## Representation and abstraction boundary

The authoritative [TLA+ kernel](../Specs/AMD64RegisterViews.tla) stores a word as
a Boolean function whose domain is `1..64`. The typed representation changes
the indexing convention but preserves every physical bit:

```text
Word       := Fin 64 -> Bool
SourceBit  := { n : Nat // 1 <= n and n <= 64 }
SourceWord := SourceBit -> Bool

sourceIndex(typedBit) := typedBit + 1
typedIndex(sourceBit) := sourceBit - 1

encode(word)(sourceBit) := word(typedIndex(sourceBit))
decode(word)(typedBit)  := word(sourceIndex(typedBit))
```

`WordWellFormed` becomes structural: a typed word has exactly the required
domain and Boolean range. Malformed TLA+ values are outside this representation
and need validation before conversion. No unknown-bit or zero-fill assumption
is introduced by the conversion.

## Views and operations

```text
GPRView := Low8 | High8 | Low16 | Low32 | Full64

offset(High8) = 8
offset(other) = 0

width(Low8) = width(High8) = 8
width(Low16) = 16
width(Low32) = 32
width(Full64) = 64

readView(word, view)[bit] :=
  if bit < width(view): word[bit + offset(view)]
  else: false

writeView64(before, payload, view)[bit] :=
  if offset(view) <= bit and bit < offset(view) + width(view):
    payload[bit - offset(view)]
  else if view = Low32:
    false
  else:
    before[bit]
```

The zero-fill in `readView` only normalizes the returned container. It does not
change the input register. The zero-fill in `writeView64` is an architectural
effect of dword GPR writes in 64-bit mode.

The view type encodes valid physical slices, not legal decoded instructions.
For example, a high-byte view exists as storage even when a particular prefix
forbids its encoding. Prefix and mode validation remain separate obligations.

## Checked properties

```text
View bounds:
  offset(view) + width(view) <= 64

Read after write:
  readView(writeView64(before, payload, view), view)[bit]
    = if bit < width(view) then payload[bit] else false

Frame:
  if view != Low32 and bit is outside view:
    writeView64(before, payload, view)[bit] = before[bit]

Dword zero extension:
  if bit >= 32:
    writeView64(before, payload, Low32)[bit] = false

Qword replacement:
  writeView64(before, payload, Full64) = payload

Representation round trips:
  decode(encode(word)) = word
  encode(decode(sourceWord)) = sourceWord
```

Example: starting with all bits set, writing zero through `High8` clears only
bits 8 through 15. Writing zero through `Low16` clears only bits 0 through 15.
Writing zero through `Low32` clears all 64 bits. These examples appear in the
TLA+ fixture independently of the generic helper's implementation.

## Correspondence and proof boundary

The Lean `Source` namespace transcribes the one-based TLA+ expressions.
The checked correspondence statements are:

```text
encode(readView(word, view))
  = Source.readView(encode(word), view)

encode(writeView64(before, payload, view))
  = Source.writeView64(encode(before), encode(payload), view)
```

These are proofs for every word and view, not finite testing. The correspondence
between `Source` and the TLA+ text is reviewed and source-hashed, not established
by a verified parser or translator. TLC and Apalache independently check the
TLA+ expressions. Neither their success nor the Lean proofs establish the full
instruction/state coverage target.

No execution trace, program counter, exception or memory state is erased from
an instruction model here: this kernel is only a pure storage operation. Its
composition into instructions, and the relationship between representable and
reachable architectural states, belong to the later instruction relation.
