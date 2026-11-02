#include <stdio.h>
#include <stdlib.h>
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <sys/user.h>
#include <unistd.h>
#include <errno.h>
int main(int argc, char **argv){
  pid_t pid = atoi(argv[1]); int samples = argc > 2 ? atoi(argv[2]) : 10;
  for(int i = 0; i < samples; i++){
    if(ptrace(PTRACE_ATTACH, pid, 0, 0) != 0){ perror("attach"); return 1; }
    int st; waitpid(pid, &st, 0);
    struct user_regs_struct r; if(ptrace(PTRACE_GETREGS, pid, 0, &r) != 0) perror("getregs");
    printf("rip %llx rsp %llx rbp %llx rax %llx rbx %llx rcx %llx rdx %llx rsi %llx rdi %llx r8 %llx r9 %llx r10 %llx r11 %llx r12 %llx r13 %llx r14 %llx r15 %llx\n", r.rip, r.rsp, r.rbp, r.rax, r.rbx, r.rcx, r.rdx, r.rsi, r.rdi, r.r8, r.r9, r.r10, r.r11, r.r12, r.r13, r.r14, r.r15);
    printf("stack:");
    for(int j = 0; j < 64; j++){ errno = 0; long w = ptrace(PTRACE_PEEKDATA, pid, r.rsp + 8*j, 0); if(errno) break; printf(" %lx", w); }
    printf("\n");
    ptrace(PTRACE_DETACH, pid, 0, 0);
    usleep(150000);
  }
  return 0;
}
