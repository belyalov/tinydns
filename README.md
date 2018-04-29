## TinyDNS [![Build Status](https://travis-ci.org/belyalov/tinydns.svg?branch=master)](https://travis-ci.org/belyalov/tinydns)
Simple and lightweight (thus - *tiny*) DNS server for tiny devices like **ESP8266** / **ESP32** running [micropython](https://github.com/micropython/micropython).
Sometimes people needs very simple DNS just to server a few domains.
For example - very common use case is **captive portal**

### Features
* Fully asynchronous using [uasyncio](https://github.com/micropython/micropython-lib/tree/master/uasyncio) library for MicroPython.
* *Tiny* memory usage. So you can run it on devices like **ESP8266 / ESP32** with 64K/96K of RAM onboard.
* Great unittest coverage. So you can be confident about quality :)

### Requirements
* [uasyncio](https://github.com/micropython/micropython-lib/tree/master/uasyncio) - micropython version of *async* library for big brother - python3.
* [uasyncio-core](https://github.com/micropython/micropython-lib/tree/master/uasyncio.core)

### Quickstart
TinyDNS comes as a compiled firmware for ESP8266 / ESP32 as well ("frozen modules"). You don't have to use it - however, it could be easiest way to try it :)
Instructions below are tested with *NodeMCU* devices. For your device instructions could be slightly different, so keep in mind.
**CAUTION**: If you proceed with installation all data on your device will **lost**!

#### Installation - ESP8266
* Download latest `firmware_esp8266.bin` from [releases](https://github.com/belyalov/tinydns/releases).
* Install `esp-tool` if you haven't done already: `pip install esptool`
* Erase flash: `esptool.py --port <UART PORT> --baud 115200 erase_flash`
* Flash firmware: `esptool.py --port <UART PORT> --baud 115200 write_flash -fm dio 0 firmware_esp8266.bin`

#### Installation - ESP32
* Download latest `firmware_esp32.bin` from [releases](https://github.com/belyalov/tinydns/releases).
* Install `esp-tool` if you haven't done already: `pip install esptool`
* Erase flash: `esptool.py --port <UART PORT> --baud 115200 erase_flash`
* Flash firmware: `esptool.py --port <UART PORT> --baud 115200 write_flash -fm dio 0x1000 firmware_esp32.bin`

#### Let's code
Coming very soon!

### Limitation / Known issues
* UDP only
* IPv4 only (therefore only **A** queries)
* Simple DNS requests only: 1 DNS query per packet (99% of DNS requests)

### Reference
#### class `Server`
* `__init__(self, domains, ttl=10, max_pkt_len=512, ignore_unknown=False)` - create `tinydns` server instance.
    * `domains` - **dict** of domains to resolve - *domain* -> *IPv4*. E.g. `{'my.com': '192.168.1.1', 'yep.com': '127.0.0.1'}`
    * `ttl` - Response TimeToLive, i.e. how long answer can be stored in the cache.
    * `max_pkt_len` - Maximum UDP packet length to serve. Due to memory constrained devices it is good to restrict datagram size.
    * `ignore_unknown` - Controls behavior for *unknown domain* case. If turned on - no error response will be generated.

* `run(self, host='127.0.0.1', port=53)` - run DNS server. Because of *tinydns* is fully async server and assumption here is you're running it as a part of some main application so it **will not** call `loop_forever()`.
    * `host` - host to listen on
    * `port` - port to listen on

More documentation and examples coming soon! :)