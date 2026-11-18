# Installation

Sample documentation for the fictional product "Quillbus", a message broker. This knowledge base is bundled so the project runs offline.

## System requirements

Quillbus 3.x requires Java 17 or newer and at least 4 GB of RAM. Java 11 is no longer supported since 3.0. On startup with an older Java version the broker exits with `UnsupportedClassVersionError`.

## Installing on Linux

Download the tarball, extract it to `/opt/quillbus` and run `bin/quillbus start`. The broker listens on port 5672 for clients and 15672 for the management console. Create a dedicated `quillbus` system user; running as root is blocked by default.

## Port already in use

If the broker fails with `Address already in use: 5672`, another process holds the client port. Find it with `ss -ltnp | grep 5672`, or change the port with `listener.port` in `conf/quillbus.conf` and restart.