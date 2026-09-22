----------------------- MODULE AMD64RegisterViews -----------------------
EXTENDS Integers, FiniteSets

\* First shared foundation for the AMD64 expansion: views of a single GPR
\* in 64-bit mode. This does NOT validate an instruction encoding, choose a
\* register, or define legacy-mode upper-bit behavior. In particular, a REX
\* prefix can forbid a high-byte view even though its storage operation exists.
\* Authority: AMD APM Volume 1, 24592 revision 3.25, sections 3.1.2 and 3.4.5.
\* Full scope, pending work and Lean correspondence boundary are recorded in
\* docs/amd64-semantics-design.md and Specs/AMD64/README.md.

\* TLA+ positions remain one-based to agree with AriadneX86_64Semantics.
\* Never calculate a 64-bit word as a TLC host integer. Arithmetic on offsets
\* below only addresses individual bits; full-width values are Boolean maps.
\* @typeAlias: amd64Word = Int -> Bool;
\* @typeAlias: amd64View = {offset: Int, width: Int};

\* @type: $amd64Word => Bool;
WordWellFormed(word) == DOMAIN word = 1..64 /\
                       \A bit \in 1..64 : word[bit] \in BOOLEAN

Low8 == [offset |-> 0, width |-> 8]
High8 == [offset |-> 8, width |-> 8]
Low16 == [offset |-> 0, width |-> 16]
Low32 == [offset |-> 0, width |-> 32]
Full64 == [offset |-> 0, width |-> 64]
Views == {Low8, High8, Low16, Low32, Full64}

\* A read returns a 64-bit container with zero above the view width. This
\* zero-fill belongs to the helper result, not to the physical source register.
\* @type: ($amd64Word, $amd64View) => $amd64Word;
ReadView(word, view) ==
  [bit \in 1..64 |-> IF bit <= view.width
                     THEN word[bit + view.offset] ELSE FALSE]

\* Payload bits 1..width replace the selected view. Byte and word writes
\* preserve every other physical bit; dword writes in 64-bit mode clear the
\* upper 32 bits. Qword writes replace the entire word. The before word is
\* an explicit parameter, so aliasing operands can both read the same snapshot.
\* Precondition: WordWellFormed(before), WordWellFormed(value), view in Views.
\* @type: ($amd64Word, $amd64Word, $amd64View) => $amd64Word;
WriteView64(before, value, view) ==
  [bit \in 1..64 |->
    IF view.offset < bit /\ bit <= view.offset + view.width
    THEN value[bit - view.offset]
    ELSE IF view = Low32 THEN FALSE ELSE before[bit]]

=============================================================================
