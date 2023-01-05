"""
MIT license
(C) Konstantin Belyalov 2018
"""
import uasyncio as asyncio
import usocket as socket
import logging
import re
import gc


DNS_QUERY_START = const(12)
log = logging.getLogger('DNS')


class Server():
    """Tiny DNS server aimed to serve very small deployments like "captive portal"
    """

    def __init__(self, domains={}, ttl=10, max_pkt_len=256, ignore_unknown=False, loop_forever=True):
        """Init DNS server class.
        Positional arguments:
            domains        -- dict of domain -> IPv4 str
        Keyword arguments:
            ttl            -- TimeToLive, i.e. expiration timeout of DNS response.
            max_pkt_len    -- Max UDP datagram size.
            ignore_unknown -- do not send response for unknown domains
        """
        self.ttl = ttl
        self.max_pkt_len = max_pkt_len
        self.ignore_unknown = ignore_unknown
        self.sock = None
        self.task = None
        self.dlist = []
        self.domains = domains.copy()
        self.__preprocess_domains()

        self.loop = asyncio.get_event_loop()
        self.loop_forever = loop_forever

    def add_domain(self, domain, ip):
        self.domains[domain] = ip
        self.__preprocess_domains()

    def __preprocess_domains(self):
        for name, ip in self.domains.items():
            bip = bytes([int(x) for x in ip.split('.')])
            self.dlist.append((re.compile(name), bip))

    def __preprocess_domains_old(self):
        # Don't use dict here - it doesn't support bytearray as key and
        # moreover, as TINY server so expecting only a few domains to resolve
        self.dlist = []
        bttl = self.ttl.to_bytes(4, 'big')
        # Pre-process domain -> IP pairs:
        # In order to consumer less memory / search efficiently we're building
        # DNS query record for each domain to be able to search for match
        # without memory allocation.
        # The same idea for DNS response - we can create it at init time -
        # to save time in run-time.
        for name, ip in self.domains.items():
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

    async def __handler(self):
        while True:
            try:
                # Wait for packet
                yield asyncio.IORead(self.sock)

                packet, addr = self.sock.recvfrom(self.max_pkt_len)
                if len(packet) < DNS_QUERY_START:
                    # Malformed packet
                    log.error("DNS query is malformed, incorrect start")
                    continue

                # handle packet
                self.handlePacket(packet, addr)

                gc.collect()
            except asyncio.CancelledError:
                # Coroutine has been canceled
                self.sock.close()
                self.sock = None
                return
            except AttributeError:
                raise
            except Exception as e:
                log.exc(e, "")

    def handlePacket(self, packet, addr):
        # Check question / answer count
        qd = int.from_bytes(packet[4:6], 'big')
        log.debug("Questions: %d", qd)
        an = int.from_bytes(packet[6:8], 'big')
        log.debug("Answers: %d", an)

        # We're tiny server - don't handle complicated queries
        if qd != 1 or an > 0:
            log.debug("DNS query is to complicated")
            return None

        if len(packet) <= DNS_QUERY_START + 4:
            # malformed packet - query must be at least 5 bytes
            log.error("DNS query is to malformed (query most be at least 16 bytes)")
            return

        # read domain name from query
        domain = ""
        # header is 12 bytes long
        head = DNS_QUERY_START
        # length of this label defined in first byte
        length = packet[head]
        while length != 0:
            label = head + 1
            # add the label to the requested domain and insert a dot after
            domain += packet[label : label + length].decode("utf-8") + "."
            # check if there is another label after this on
            head += length + 1
            length = packet[head]
        # advance head once more, so that we are beyond the domain part
        head += 1

        log.debug("Domain: %s", domain)

        # get query type - only A/* supported
        qtype = int.from_bytes(packet[head:head+2], 'big')
        log.debug("qtype: %d", qtype)

        # verify query type 
        if qtype not in [0x01, 0xff]:
            # unsupported query type, AAAA, CNAME, etc
            # Flags: 0x8180 Standard query response, No error
            resp = bytearray(packet)
            resp[2:4] = b'\x81\x80'
            self.sock.sendto(resp, addr)
            log.debug("Unsupported query type: %d", qtype)
            return

        # query type is of A type, try to get matching domain!
        matchDomain = self.getMatchingDomain(domain)
        if not matchDomain:
            # no matching domain
            resp = bytearray(packet)
            # Flags: 0x8183 Standard query response, No such name
            resp[2:4] = b'\x81\x83'
            self.sock.sendto(resp, addr)
            return

        # ????
        if not matchDomain and not self.ignore_unknown:
            return

        # Prepare response right from request :)
        # copy the ID from incoming request
        resp = packet[:2]
        # set response flags (assume RD=1 from request)
        resp += b"\x81\x80"
        # copy over QDCOUNT and set ANCOUNT equal
        resp += packet[4:6] + packet[4:6]
        # set NSCOUNT and ARCOUNT to 0
        resp += b"\x00\x00\x00\x00"

        # ** create the answer body **
        # respond with original domain name question
        # take from question start + qtype and qclass
        resp += packet[DNS_QUERY_START:head+2+2]
        # pointer back to domain name (at byte 12)
        resp += b"\xC0\x0C"
        # set TYPE and CLASS (A record and IN class)
        resp += b"\x00\x01\x00\x01"
        # set TTL to 60sec
        resp += b"\x00\x00\x00\x3C"
        # set response length to 4 bytes (to hold one IPv4 address)
        resp += b"\x00\x04"
        # now actually send the IP address as 4 bytes (without the "."s)
        resp += matchDomain[1]

        self.sock.sendto(resp, addr)

    def getMatchingDomain(self, domain):
        domain = domain[:-1]

        for d in self.dlist:
            if d[0].match(domain):
                return d
        return None
        

    def run(self, host='127.0.0.1', port=53):
        # Start UDP server
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = socket.getaddrinfo(host, port, 0, socket.SOCK_DGRAM)[0][-1]
        sock.setblocking(False)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(addr)
        self.sock = sock
        self.task = self.__handler()

        self.loop.create_task(self.task)
        if self.loop_forever:
            self.loop.run_forever()

    def shutdown(self):
        if self.task:
            asyncio.cancel(self.task)
            self.task = None
