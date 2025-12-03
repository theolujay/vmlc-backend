```

docker exec -d 42f3acbe6d70 pg_dump -U verboheit_staging -d vmlc_staging -Fc -b -v > backup_20251106.dump
│      │     │ │            │        │                    │               ││  │  │   │
│      │     │ │            │        │                    │               ││  │  │   └─ Output file.
│      │     │ │            │        │                    │               ││  │  └───── Specifies verbose mode.
│      │     │ │            │        │                    │               ││  └──────── Include large objects in the dump.
│      │     │ │            │        │                    │               │└─────────── Out put a custom-format archive suitable for input into pg_restore
│      │     │ │            │        │                    │               └──────────── Selects the format of the output.
│      │     │ │            │        │                    └──────────────────────────── Specifies the name of the database to connect to. 
│      │     │ │            │        └───────────────────────────────────────────────── User name to connect as.
│      │     │ │            └────────────────────────────────────────────────────────── Export a PostgreSQL database as an SQL script or to other formats
│      │     │ └─────────────────────────────────────────────────────────────────────── Container ID 
│      │     └───────────────────────────────────────────────────────────────────────── Detached mode: run command in the background
└──────└─────────────────────────────────────────────────────────────────────────────── Execute a command in a running container
```