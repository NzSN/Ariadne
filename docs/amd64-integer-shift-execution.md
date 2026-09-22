# AMD64 shift and rotate execution binding

This checkpoint binds all 116 pinned Volume 3 shift and rotate rows to concrete
CPU register effects. The source evidence and grouped form IDs are recorded in
`Specs/AMD64/integer-shift-form-supplement.json`. Original reg/mem alternatives
remain visible. A register instance executes; a memory instance returns
`modeling-unavailable` until MachineAccess provides resolved bytes and events.

Every operand is read from the pre-state before any write. This covers `SHL
CL,CL`, overlapping SHLD/SHRD operands, and BMI2 instructions whose destination,
source and count name the same register. A masked legacy count of zero skips the
destination and flag writes entirely. BMI2 instructions still write their
separate destination when their masked count is zero.

Legacy counts use five bits, or six for a 64-bit operand. Rotate value selection
uses the effective ring count while flag definedness uses the masked count.
SHLD/SHRD keep relational destinations and flags when the masked count exceeds
the operand width. BMI2 forms require protected, compatibility or long mode,
the BMI2 feature, `VEX.L=0`, and a `VEX.W` value matching the 32/64-bit row.

Validation combines Lean build and axiom audit, Snowcat typechecking, and a TLC
fixture covering all form bindings, source/destination aliasing, count zero,
ROL counts 8 and 9, an RCL full-ring count, two distinct SHLD16 oversize
destinations, and BMI2 feature/mode/encoding gates.
