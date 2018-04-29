#!/usr/bin/env micropython
"""
Unittests for simple DNS server
MIT license
(C) Konstantin Belyalov 2018
"""

import unittest
import tinydns
from uasyncio.core import IORead


# Transaction ID: 0x4929
# Flags: 0x0100 Standard query
# Questions: 1
# Answer RRs: 0
# Authority RRs: 0
# Additional RRs: 0
# Queries
#   ya.com: type A, class IN
ya_com_rq = b'\x49\x29\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x02\x79\x61\x03' \
            b'\x63\x6f\x6d\x00\x00\x01\x00\x01'

# The same thing, but with type ALL (0xff), class IN
ya_com_rq_all = b'\x49\x29\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x02\x79\x61\x03' \
                b'\x63\x6f\x6d\x00\x00\xff\x00\x01'

# The same, query type MX
ya_com_rq_mx = b'\x49\x29\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x02\x79\x61\x03' \
               b'\x63\x6f\x6d\x00\x00\x0f\x00\x01'

# DNS Response, partial packet - without TTL / DataLen / IP address at the end
ya_com_rp = b'\x49\x29\x85\x80\x00\x01\x00\x01\x00\x00\x00\x00\x02\x79\x61\x03' \
            b'\x63\x6f\x6d\x00\x00\x01\x00\x01\xc0\x0c\x00\x01\x00\x01'

# DNS Response for unknown domain name case
ya_com_rp2 = b'\x49\x29\x81\x83\x00\x01\x00\x00\x00\x00\x00\x00\x02\x79\x61\x03' \
             b'\x63\x6f\x6d\x00\x00\x01\x00\x01'

# Partial response for ALL class
ya_com_rp_all = b'\x49\x29\x85\x80\x00\x01\x00\x01\x00\x00\x00\x00\x02\x79\x61\x03' \
                b'\x63\x6f\x6d\x00\x00\xff\x00\x01\xc0\x0c\x00\x01\x00\x01'

# Response for MX class, full pakcet
ya_com_rp_mx = b'\x49\x29\x81\x80\x00\x01\x00\x00\x00\x00\x00\x00\x02\x79\x61\x03' \
               b'\x63\x6f\x6d\x00\x00\x0f\x00\x01'

# Transaction ID: 0x4147
# Flags: 0x0100 Standard query
# Questions: 1
# Answer RRs: 0
# Authority RRs: 0
# Additional RRs: 0
# Queries
#   google.com: type A, class IN
google_rq = b'\x41\x47\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x06\x67\x6f\x6f' \
            b'\x67\x6c\x65\x03\x63\x6f\x6d\x00\x00\x01\x00\x01'

google_rp = b'\x41\x47\x85\x80\x00\x01\x00\x01\x00\x00\x00\x00\x06\x67\x6f\x6f' \
            b'\x67\x6c\x65\x03\x63\x6f\x6d\x00\x00\x01\x00\x01\xc0\x0c\x00\x01' \
            b'\x00\x01'

# "Unknown" domain
blah_rq = b'\x09\x73\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x06\x62\x68\x68' \
          b'\x68\x68\x68\x03\x63\x6f\x6d\x00\x00\x01\x00\x01'


def mk_dns_response(packet, addr, ttl):
    ip = bytes([int(x) for x in addr.split('.')])
    return b''.join([packet, ttl.to_bytes(4, 'big'), b'\x00\x04', ip])


class MockSocket():
    """Mock implementation for system socket"""

    def __init__(self, resp):
        self.resp = resp
        self.pack = None
        self.addr = None

    def recvfrom(self, max_recv):
        self.max_recv = max_recv
        # packet, address
        return self.resp, 100

    def sendto(self, pack, addr):
        self.pack = pack
        self.addr = addr


class DnsTests(unittest.TestCase):
    """Simple sanity test - verify that "response" generates right packets"""

    def setUp(self):
        self.dns = tinydns.dnsserver(domains={'ya.com': '192.168.5.1',
                                              'google.com': '1.1.1.1'}, ttl=33)

    def testYa(self):
        # Prepare mock socket to send ya.com query
        msock = MockSocket(ya_com_rq)
        self.dns.sock = msock
        # Emulate that receiving of packet
        itr = self.dns.__handler()
        self.assertIsInstance(next(itr), IORead)
        self.assertIsInstance(next(itr), IORead)
        # Check result - response should be "sent"
        self.assertEqual(msock.addr, 100)
        self.assertEqual(msock.pack, mk_dns_response(ya_com_rp, '192.168.5.1', 33))

    def testYaTypeAll(self):
        # Prepare mock socket to send ya.com query
        msock = MockSocket(ya_com_rq_all)
        self.dns.sock = msock
        # Emulate that receiving of packet
        itr = self.dns.__handler()
        self.assertIsInstance(next(itr), IORead)
        self.assertIsInstance(next(itr), IORead)
        # Check result - response should be "sent"
        self.assertEqual(msock.addr, 100)
        self.assertEqual(msock.pack, mk_dns_response(ya_com_rp_all, '192.168.5.1', 33))

    def testYaTypeMX(self):
        # Prepare mock socket to send ya.com query
        msock = MockSocket(ya_com_rq_mx)
        self.dns.sock = msock
        # Emulate that receiving of packet
        itr = self.dns.__handler()
        self.assertIsInstance(next(itr), IORead)
        self.assertIsInstance(next(itr), IORead)
        # Check result - response should be "sent" without answers
        self.assertEqual(msock.addr, 100)
        self.assertEqual(msock.pack, ya_com_rp_mx)

    def testGoogle(self):
        # Prepare mock socket to send ya.com query
        msock = MockSocket(google_rq)
        self.dns.sock = msock
        # Emulate that receiving of packet
        itr = self.dns.__handler()
        self.assertIsInstance(next(itr), IORead)
        self.assertIsInstance(next(itr), IORead)
        # Check result - response should be "sent"
        self.assertEqual(msock.addr, 100)
        self.assertEqual(msock.pack, mk_dns_response(google_rp, '1.1.1.1', 33))

    def testMalformedShortPacket(self):
        msock = MockSocket(b'dshfjsd')
        self.dns.sock = msock
        itr = self.dns.__handler()
        self.assertIsInstance(next(itr), IORead)
        self.assertIsInstance(next(itr), IORead)
        # Check result - should be not response sent
        self.assertEqual(msock.addr, None)
        self.assertEqual(msock.pack, None)

    def testMalformedShortQuery(self):
        msock = MockSocket(ya_com_rq[:14])
        self.dns.sock = msock
        itr = self.dns.__handler()
        self.assertIsInstance(next(itr), IORead)
        self.assertIsInstance(next(itr), IORead)
        # Check result - should be not response sent
        self.assertEqual(msock.addr, None)
        self.assertEqual(msock.pack, None)

    def testUnknown(self):
        # Re-create server with empty list
        self.dns = tinydns.dnsserver({})
        # Prepare mock socket to send ya.com query
        msock = MockSocket(ya_com_rq)
        self.dns.sock = msock
        # Emulate that receiving of packet
        itr = self.dns.__handler()
        self.assertIsInstance(next(itr), IORead)
        self.assertIsInstance(next(itr), IORead)
        # Check result
        self.assertEqual(msock.addr, 100)
        self.assertEqual(msock.pack, ya_com_rp2)

    def testUnknownIgnore(self):
        # Re-create server with empty list
        self.dns = tinydns.dnsserver({}, ignore_unknown=True)
        # Prepare mock socket to send ya.com query
        msock = MockSocket(ya_com_rq)
        self.dns.sock = msock
        # Emulate that receiving of packet
        itr = self.dns.__handler()
        self.assertIsInstance(next(itr), IORead)
        self.assertIsInstance(next(itr), IORead)
        # Check result - should be not response sent
        self.assertEqual(msock.addr, None)
        self.assertEqual(msock.pack, None)


if __name__ == '__main__':
    unittest.main()
