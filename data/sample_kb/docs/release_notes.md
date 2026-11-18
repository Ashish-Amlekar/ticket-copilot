# Release notes

## 3.3.0

Added `quillbus drain`. Fixed a memory leak in the management console when more than 500 queues exist. Default `ack.timeout` changed from 60 to 30 seconds.

## 3.2.1

Fixed `TLS_KEY_TOO_WEAK` being raised for valid ECDSA certificates. ECDSA P-256 keys are now accepted.

## 3.0.0

Dropped Java 11 support. Renamed `max_conn` to `max_connections`; the old name is ignored silently, so check your config after upgrading. Removed the legacy v1 client protocol.