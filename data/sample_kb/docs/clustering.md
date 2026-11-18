# Clustering and high availability

## Forming a cluster

A cluster needs at least three nodes. Set the same `cluster.cookie` on every node and list peers in `cluster.nodes`. Nodes must resolve each other by hostname; IP-only setups are not supported.

## Split brain

If a network partition occurs the cluster pauses the minority side by default (`partition.strategy = pause_minority`). Paused nodes reject clients until the partition heals. Do not switch to `ignore` in production; it can cause divergent queues.

## Rolling upgrades

Upgrade one node at a time, minor versions only (for example 3.2 to 3.3). Upgrading across a major version requires a full shutdown. Drain connections with `bin/quillbus drain` before stopping a node.