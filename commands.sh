## Some helpful commands

# Add ELF section with objcopy (not MacOS)
#llvm-objcopy -I binary -B default -O x86_64-apple-macosx13.0.0 --rename-section .data=.abom,noload,readonly,contents prog.out.abom prog.out.abom.o

# Compile assembly to object
clang -c -o prog.out.abom.o prog.out.abom.s

# Dump binary section to file
llvm-objcopy --dump-section=__ABOM,__abom=prog.out.abom prog.out

# List binary sections
objdump -x prog.out