#!/usr/bin/env python3
"""Forward one local TCP port to another.

Model configs pin the Ollama endpoint they were measured against: the seven
evaluated on the A100 carry port 11500, the seven from spark-3 use the default
11434. Running any of them on the other machine would otherwise mean editing the
config, which would rewrite the record of where the original numbers came from.

Bridging the port instead keeps a machine detail out of files that describe
results.

    python tools/portbridge.py 11500 11434    # serve :11500, forward to :11434
"""

from __future__ import annotations

import socket
import sys
import threading


def pipe(a: socket.socket, b: socket.socket) -> None:
    try:
        while True:
            data = a.recv(65536)
            if not data:
                break
            b.sendall(data)
    except OSError:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            s.close()


def handle(client: socket.socket, dst: tuple[str, int]) -> None:
    try:
        upstream = socket.create_connection(dst)
    except OSError:
        client.close()
        return
    threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()
    threading.Thread(target=pipe, args=(upstream, client), daemon=True).start()


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: portbridge.py <listen_port> <forward_port>")
    listen, forward = int(sys.argv[1]), int(sys.argv[2])
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", listen))
    srv.listen(128)
    print(f"bridging 127.0.0.1:{listen} -> 127.0.0.1:{forward}", flush=True)
    while True:
        client, _ = srv.accept()
        handle(client, ("127.0.0.1", forward))


if __name__ == "__main__":
    main()
