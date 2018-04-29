"""
MIT license
(C) Konstantin Belyalov 2018
"""
import uasyncio as asyncio
import usocket as socket
import gc
from uasyncio.core import IORead


DNS_QUERY_START = const(12)


class dnsserver():
    """Tiny DNS server aimed to serve very small deployments like "captive portal"
    """

    def __init__(self, domains, ttl=10, max_pkt_len=512, ignore_unknown=False):
        """Init DNS server class.
        Positional arguments:
            domains        -- dict of domain -> IPv4 str
        Keyword arguments:
            ttl            -- TimeToLive, i.e. expiration timeout of DNS response.
            max_pkt_len    -- Max UDP datagram size.
            ignore_unknown -- do not send response for unknown domains
        """
        self.max_pkt_len = max_pkt_len
        self.ignore_unknown = ignore_unknown
        self.sock = None
        # Don't use dict here - it doesn't support bytearray as key and
        # moreover, as TINY server so expecting only a few domains to resolve
        self.dlist = []
        bttl = ttl.to_bytes(4, 'big')
        # Pre-process domain -> IP pairs:
        # In order to consumer less memory / search efficiently we're building
        # DNS query record for each domain to be able to search for match
        # without memory allocation.
        # The same idea for DNS response - we can create it at init time -
        # to save time in run-time.
        for name, ip in domains.items():
            # Convert domain into DNS style - len / label
            req = []
            for part in name.split('.'):
                req.append(len(part).to_bytes(1, 'big'))
                req.append(part.encode())
            # add tail:
            # - zero len label - indicating end of domain
            # - TYPE A
            # - CLASS IN
            req.append(b'\x00\x00\x01\x00\x01')
            # Generate DNS answer section
            # Convert IP to binary format
            bip = bytes([int(x) for x in ip.split('.')])
            # PTR A IN TTL DATA 4 <IP>
            resp = b'\xc0\x0c\x00\x01\x00\x01' + bttl + b'\x00\x04' + bip
            # Insert tuple (dns question -> partial dns response)
            self.dlist.append((b''.join(req), resp))
        gc.collect()

    def __handler(self):
        while True:
            try:
                # Wait for packet
                yield IORead(self.sock)
                packet, addr = self.sock.recvfrom(self.max_pkt_len)
                if len(packet) < DNS_QUERY_START:
                    # Malformed packet
                    continue
                # Check question / answer count
                qd = int.from_bytes(packet[4:6], 'big')
                an = int.from_bytes(packet[6:8], 'big')
                # We're tiny server - don't handle complicated queries
                if qd != 1 or an > 0:
                    return None
                query = bytearray(packet[DNS_QUERY_START:])
                if len(query) <= 4:
                    # malformed packet - query must be at least 5 bytes
                    continue
                # verify query type - only A/* supported
                qtype = int.from_bytes(query[-4:-2], 'big')
                if qtype not in [0x01, 0xff]:
                    # unsupported query type, AAAA, CNAME, etc
                    # Flags: 0x8180 Standard query response, No error
                    resp = bytearray(packet)
                    resp[2:4] = b'\x81\x80'
                    self.sock.sendto(resp, addr)
                    continue
                # sometimes request may query for ALL records (0xff)
                # since we're only support A records - simply override it to 0x01
                query[-4:-2] = b'\x00\x01'
                resp = None
                for d in self.dlist:
                    if d[0] == query:
                        # Prepare response right from request :)
                        resp = bytearray(len(packet) + len(d[1]))
                        resp[:len(packet)] = packet
                        # Adjust flags
                        resp[2:4] = b'\x85\x80'  # Flags and codes
                        resp[6:8] = b'\x00\x01'  # Answer record count
                        # Add answer
                        resp[len(packet):] = d[1]
                        self.sock.sendto(resp, addr)
                        break
                if not resp and not self.ignore_unknown:
                    # no such domain, just send req back with error flag set
                    resp = bytearray(packet)
                    # Flags: 0x8183 Standard query response, No such name
                    resp[2:4] = b'\x81\x83'
                    self.sock.sendto(resp, addr)
                gc.collect()
            except Exception as e:
                print('DNS server error: "{}", ignoring.'.format(e))
                raise

    def run(self, host='127.0.0.1', port=53):
        # Start UDP server
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = socket.getaddrinfo(host, port, 0, socket.SOCK_DGRAM)[0][-1]
        sock.setblocking(False)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(addr)
        self.sock = sock
        asyncio.get_event_loop().create_task(self.__handler())

    def shutdown(self):
        if self.sock:
            self.sock.close()
            self.sock = None
