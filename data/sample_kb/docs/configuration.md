# Configuration

## Connection limits

The setting `max_connections` in `conf/quillbus.conf` caps simultaneous client connections. The default is 1000. When the limit is reached new clients receive `CONNECTION_REFUSED: limit reached`. Raise the value together with the OS file descriptor limit (`ulimit -n`), which must be at least `max_connections * 2`.

## Message retention

Messages are kept until consumed or until `retention.hours` expires (default 72). Setting `retention.hours = 0` disables expiry, which can fill the disk. Expired messages are moved to the dead-letter queue when `dlq.enabled = true`.

## TLS

Enable TLS with `tls.enabled = true` and set `tls.keystore` and `tls.keystore.password`. Clients must then connect on port 5671. Certificates must use RSA 2048 bit or stronger; weaker keys are rejected at startup with `TLS_KEY_TOO_WEAK`.

## Memory settings

The heap is set with `QB_HEAP` (for example `QB_HEAP=4g`). Do not set it above 75% of physical RAM, otherwise the OS may kill the process (OOM killer).