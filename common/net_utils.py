def recv_exact(sock, n: int) -> bytes:
    """
    TCP is a byte-stream, so a single recv(n) may return fewer than n bytes.
    Our protocol messages have fixed sizes (e.g., 38/10/9 bytes),
    so we loop until exactly n bytes are received.
    """
    data = bytearray() # accumulate partial TCP reads efficiently
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Socket closed while reading")
        data.extend(chunk)
    return bytes(data)
