; Native LLVM IR fixture. The input is directly supplied IR, not lifted code.
define i32 @diamond(ptr %ptr, i1 %cond, ptr %callee) {
entry:
  br i1 %cond, label %left, label %right

left:
  %left.value = add i32 1, 2
  store i32 %left.value, ptr %ptr
  br label %join

right:
  %right.value = add i32 3, 4
  store i32 %right.value, ptr %ptr
  br label %join

join:
  %joined.value = phi i32 [ %left.value, %left ], [ %right.value, %right ]
  call void %callee(i32 %joined.value)
  %loaded.value = load i32, ptr %ptr
  %result.value = add i32 %joined.value, %loaded.value
  ret i32 %result.value
}
