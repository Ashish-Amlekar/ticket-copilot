# Troubleshooting

## Consumers stop receiving messages

If consumers stall while the queue depth grows, check for unacknowledged messages. A consumer that fetches messages but never acknowledges them holds them until `ack.timeout` (default 30 seconds). Lower `prefetch` to 10 and make sure the client calls `ack()` after processing. A stuck consumer can be identified in the management console under Connections, column `unacked`.

## High memory usage

Memory grows when queues are unbounded. Set `queue.max_length` to cap queue size and choose `overflow = reject` or `overflow = drop_head`. Persistent queues with large backlogs also increase heap usage because the index is kept in memory.

## Disk full alarm

When free disk space drops below `disk.free_limit` (default 1 GB) the broker blocks publishers and logs `DISK_ALARM`. Free space or raise the limit's headroom, then publishing resumes automatically. Check `retention.hours` if the disk fills repeatedly.

## Slow publishing

Publisher throughput drops sharply when `sync_publish = true`, because every message waits for a disk flush. Use publisher confirms in batches, or set `sync_publish = false` if losing the last second of messages on a crash is acceptable.