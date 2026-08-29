// AegisForecast production telemetry probe (eBPF / XDP reference).
//
// In production this attaches to a network interface (SPAN/TAP port or the
// host NIC) and maintains per-flow 5-second bidirectional statistics in
// kernel maps - the zero-upload design: only aggregated stats are read by
// user space; raw packets never leave the kernel and are never stored.
//
// Build (Linux, kernel >= 5.15, clang >= 14):
//   clang -O2 -target bpf -c aegis_flow_kern.c -o aegis_flow_kern.o
// Attach with a tc/xdp loader (e.g. `bpftool` or libbpf) and read the
// AEGIS_FLOW_MAP every 5s from user space.
//
// This file is the production reference for the kernel hook; the lab/demo
// uses the Python Scapy simulator in aegis/simulator with identical output
// schema, so model + backend code paths are unchanged between lab and prod.

#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

// ---- flow key: canonical 5-tuple (lower endpoint wins) --------------------
struct flow_key {
    __be32 ip_a;
    __be32 ip_b;
    __be16 port_a;
    __be16 port_b;
    __u8   proto;
    __u8   pad[3];
};

// ---- rolling flow stats (mirrors aegis/flows FlowStats) --------------------
struct flow_stats {
    __u32 pkts;
    __u32 bytes;
    __u32 syn;
    __u32 synack;
    __u32 rst;
    __u32 fin;
    __u32 psh;
    __u32 ack;
    __u64 last_ns;
};

// BPF hash map: bounded to prevent memory explosion (kernel safety check).
struct {
    __uint(type, BPF_MAP_TYPE_LRU_HASH);
    __uint(max_entries, 65536);
    __type(key, struct flow_key);
    __type(value, struct flow_stats);
} aegis_flow_map SEC(".maps");

static __always_inline void canon(struct flow_key *k, __be32 sip, __be32 dip,
                                   __be16 sp, __be16 dp, __u8 proto) {
    if (bpf_ntohl(sip) <= bpf_ntohl(dip)) {
        k->ip_a = sip; k->ip_b = dip; k->port_a = sp; k->port_b = dp;
    } else {
        k->ip_a = dip; k->ip_b = sip; k->port_a = dp; k->port_b = sp;
    }
    k->proto = proto;
}

SEC("xdp")
int aegis_flow_probe(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;
    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end || ip->ihl < 5)
        return XDP_PASS;

    struct flow_key k = {};
    __u8 tcp_flags = 0;
    __u16 sport = 0, dport = 0;
    __u32 len = bpf_ntohs(ip->tot_len);

    if (ip->protocol == IPPROTO_TCP) {
        struct tcphdr *tcp = (void *)ip + ip->ihl * 4;
        if ((void *)(tcp + 1) > data_end)
            return XDP_PASS;
        sport = tcp->source; dport = tcp->dest;
        tcp_flags = ((__u8 *)tcp)[13];
        canon(&k, ip->saddr, ip->daddr, sport, dport, IPPROTO_TCP);
    } else if (ip->protocol == IPPROTO_UDP) {
        struct udphdr *udp = (void *)ip + ip->ihl * 4;
        if ((void *)(udp + 1) > data_end)
            return XDP_PASS;
        sport = udp->source; dport = udp->dest;
        canon(&k, ip->saddr, ip->daddr, sport, dport, IPPROTO_UDP);
    } else {
        return XDP_PASS;
    }

    // fold into rolling stats - in-kernel only, zero-copy, no pcap storage
    struct flow_stats *st = bpf_map_lookup_elem(&aegis_flow_map, &k);
    if (st) {
        __sync_fetch_and_add(&st->pkts, 1);
        __sync_fetch_and_add(&st->bytes, len);
        if (tcp_flags & 0x02) __sync_fetch_and_add(&st->syn, 1);
        if ((tcp_flags & 0x12) == 0x12) __sync_fetch_and_add(&st->synack, 1);
        if (tcp_flags & 0x04) __sync_fetch_and_add(&st->rst, 1);
        if (tcp_flags & 0x01) __sync_fetch_and_add(&st->fin, 1);
        if (tcp_flags & 0x08) __sync_fetch_and_add(&st->psh, 1);
        if (tcp_flags & 0x10) __sync_fetch_and_add(&st->ack, 1);
        st->last_ns = bpf_ktime_get_ns();
    } else {
        struct flow_stats fresh = { .pkts = 1, .bytes = len, .last_ns = bpf_ktime_get_ns() };
        if (tcp_flags & 0x02) fresh.syn = 1;
        if ((tcp_flags & 0x12) == 0x12) fresh.synack = 1;
        if (tcp_flags & 0x04) fresh.rst = 1;
        if (tcp_flags & 0x01) fresh.fin = 1;
        if (tcp_flags & 0x08) fresh.psh = 1;
        if (tcp_flags & 0x10) fresh.ack = 1;
        bpf_map_update_elem(&aegis_flow_map, &k, &fresh, BPF_NOEXIST);
    }
    return XDP_PASS;
}

char LICENSE[] SEC("license") = "GPL";
