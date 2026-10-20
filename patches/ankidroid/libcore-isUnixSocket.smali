# SPDX-License-Identifier: GPL-2.0-or-later
# Bundled libcore compatibility: getsockname identifies the family without SO_DOMAIN.
.method public static isUnixSocket(Ljava/io/FileDescriptor;)Z
    .registers 2
    .annotation system Ldalvik/annotation/Throws;
        value = {
            Landroid/system/ErrnoException;
        }
    .end annotation
    sget-object v0, Llibcore/io/Libcore;->rawOs:Llibcore/io/Os;
    invoke-interface {v0, p0}, Llibcore/io/Os;->getsockname(Ljava/io/FileDescriptor;)Ljava/net/SocketAddress;
    move-result-object p0
    instance-of p0, p0, Landroid/system/UnixSocketAddress;
    return p0
.end method
