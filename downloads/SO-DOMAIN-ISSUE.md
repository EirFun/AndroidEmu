Suggested upstream issue: Implement Linux SO_DOMAIN for libcore ServerSocket.accept

On Husk 3.0 build 129, AnkiDroid's NanoHTTPD listener reports:

```
java.net.SocketException: getsockopt failed: ENOPROTOOPT (Protocol not available)
  at java.net.PlainSocketImpl.socketAccept
Caused by: android.system.ErrnoException: getsockopt failed: ENOPROTOOPT
  at libcore.io.BlockGuardOs.isUnixSocket
```

`BlockGuardOs.accept()` checks Linux `SOL_SOCKET/SO_DOMAIN` before calling the native accept operation. Husk's `opt_to_darwin()` has no entry for option 39, so `b_getsockopt()` returns `ENOPROTOOPT`. A pending connection remains queued; NanoHTTPD catches the resulting IOException and retries without backoff. This provides a mechanism for repeated exceptions and rapid allocation growth observed on the listener thread. Separate blocked-close signaling issues can affect shutdown.

The source fix adds a `SO_DOMAIN` branch using `getsockname()` and converts the host family through the existing `dom_from_darwin()`. It preserves ordinary socket options and error reporting. The production branch is exercised by `python3 tests/translation-layer/test_socket_domain.py` with real IPv4, IPv6 and Unix sockets on the host; Darwin/iOS still requires native-build validation.

Native source fix commit: https://github.com/EirFun/AndroidEmu/commit/a1ae4b2

The downloadable test v10 IPA uses a managed libcore `getsockname()` alternative because no native iOS build was performed. That is distinct from shipping the native C fix. No upstream PR has been opened from this source-copy repository.
