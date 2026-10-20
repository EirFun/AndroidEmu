#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile the production SO_DOMAIN branch with portable host shims and real sockets."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[2] / 'src/translation-layer-next/husk-tl-bionic-net.c').read_text()
start = source.index('static int b_getsockopt(')
end = source.index('\n}', start) + 2
function = source[start:end]
family_start = source.index('static int dom_from_darwin(')
family_end = source.index('\n', family_start)
family = source[family_start:family_end]
fixture = r'''
#include <assert.h>
#include <stdio.h>
#include <stdbool.h>
#include <errno.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#define G_SOL_SOCKET 1
#define G_SO_DOMAIN 39
#define G_AF_UNIX 1
#define G_AF_INET 2
#define G_AF_INET6 10
#define G_ENOPROTOOPT 92
#define TL_ERRNO_BEGIN()
#define TL_ERRNO_END()
#define NTRACE(...) do { if (0) fprintf(stderr, __VA_ARGS__); } while (0)
static void tl_set_guest_errno(int e) { errno = e; }
static int tl_errno_to_guest(int e) { return e; }
static bool opt_to_darwin(int level, int name, int *dl, int *dn) {
    if (level == G_SOL_SOCKET && name == 3) { *dl=SOL_SOCKET; *dn=SO_TYPE; return true; }
    return false;
}
'''
fixture += family + '\n' + function
fixture += r'''
int main(void) {
    int families[] = {AF_INET, AF_INET6, AF_UNIX};
    int expected[] = {G_AF_INET, G_AF_INET6, G_AF_UNIX};
    for (int i=0; i<3; ++i) {
        int fd=socket(families[i],SOCK_STREAM,0); assert(fd>=0);
        int domain=-1; socklen_t length=sizeof(domain);
        assert(b_getsockopt(fd,G_SOL_SOCKET,G_SO_DOMAIN,&domain,&length)==0);
        assert(domain==expected[i] && length==sizeof(domain));
        int type=-1; length=sizeof(type);
        assert(b_getsockopt(fd,G_SOL_SOCKET,3,&type,&length)==0 && type==SOCK_STREAM);
        length=0; assert(b_getsockopt(fd,G_SOL_SOCKET,G_SO_DOMAIN,NULL,&length)==0 && length==0);
        length=sizeof(domain); errno=0;
        assert(b_getsockopt(fd,G_SOL_SOCKET,G_SO_DOMAIN,NULL,&length)==-1 && errno==EFAULT);
        close(fd);
    }
    int domain; socklen_t length=sizeof(domain); errno=0;
    assert(b_getsockopt(-1,G_SOL_SOCKET,G_SO_DOMAIN,&domain,&length)==-1 && errno==EBADF);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary)
    (root/'test.c').write_text(fixture)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(root/'test.c'),'-o',str(root/'test')],check=True)
    subprocess.run([str(root/'test')],check=True)
print('PASS: production SO_DOMAIN branch handles IPv4/IPv6/Unix, zero length, invalid buffers/descriptors and preserves SO_TYPE')
