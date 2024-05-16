Custom NDN Traffic Generator Stack Configuration
====

## General stack configuration for Soft-State Interests experimentation
### Client
```YAML
- { name: ndn-traffic, role: client, content: <requested content name>, prefix: yes, sequence: no, fresh: no, soft: yes, sync_start: yes, sync_stop: yes, interval: <interest send interval in MICRO seconds>, int_lifetime: <interest lifetime in MILLI seconds. Time must be equal to interval>, level: 1, signal: yes, use_core: 2 }
```

### Push Source
```YAML
- { name: ndn-traffic, role: push_source, content: <offered content name>, bytes: <byte-size>, content_delay: 0, generation_interval: <interval in us>, freshness_period: 0, level: 0, signal: yes, use_core: 2 }
```

## Client Configuration Details
Example configuration:
```YAML
- { name: ndn-traffic, role: client, content: /node-2/prio3/test, prefix: yes, sequence: no, fresh: yes, soft: yes, sync_start: yes, sync_stop: yes, interval: 2000000, level: 1, signal: yes, use_core: 2 }
```
* `name: ndn-traffic` specifies that we use the ndn-traffic service type
* `role: client` specifies that we use the client variant
* `content: /node-2/prio3/test` specifies the content name we want to request or subscribe to
* `prefix: yes` set to yes specifies that the name element in the interest can be a prefix and does not need to match the exact full name of the requested data
* `sequence: no` specifies wheter to add a sequence number to the name
* `fresh: yes` specifies if data must be fresh
* `soft: yes` specifies if the soft interests are to be used
* `int_lifetime: 2000` the lifetime of the interest in milliseconds. If soft interests used, should be set to the exact time as the `interval`
* `sync_start: yes` synchronize app start with experiment start
* `sync_stop: yes` synchronize app end with experiment end
* `interval: 2000000` how often to send interests in microseconds
* `level: 1` start level
* `signal: yes` use signal
* `use_core: 2` which CPU core to use

## Push Source Configuration Details
Example configuration:
```YAML
- { name: ndn-traffic, role: push_source, content: /node-2/prio3/test, bytes: 1250, content_delay: 0, generation_interval: 100, freshness_period: 1, level: 0, signal: yes, use_core: 2 }
```
* `name: ndn-traffic` specifies that we use the ndn-traffic service type
* `role: push_source` specifies that we use the push_source variant
* `content: /node-2/prio3/test` specifies the content name we offer
* `bytes: 1250` number of bytes we offer
* `content_delay: 0` content generation delay (after interest reception) in microseconds - set to 0 as not really relevant for push source
* `generation_interval: 100` content generation interval in microseconds
* `freshness_period: 1` time for which the content is fresh
* `level: 1` start level
* `signal: yes` use signal
* `use_core: 2` which CPU core to use