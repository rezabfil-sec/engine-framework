# Service Name
Please fill this file with a description of the service;
the following is an example of a description.

## Manual
Usage in stack:
```yaml
- { name: 'service-name', mode: 'client', rep?: 64 }
```

Notes:
- `mode` is the mode of the service (required)
    - `client` for client mode
    - `server` for server mode
- `rep` is the number of repetitions (optional, default: 64)
