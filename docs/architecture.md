# Architecture

```text
Browser dashboard -> private API/control service -> orchestration -> evidence JSON
                                           |
                                           v
                conversion / llama-bench / quality gate / llama-server on Arm64 VM
                                           |
                                           v
                         GGUF model + Arm KleidiAI CPU backend
```

The API runs as a private `systemd` service on the Oracle Cloud Arm64 Linux VM
next to the model. The browser dashboard opens from a laptop through an SSH
local tunnel. Preview mode may show a candidate plan and sample report format,
but only the Arm worker can create measured evidence or enable serving.
