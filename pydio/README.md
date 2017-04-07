python
======

Sync daemon listening for both local folder and server changes and continuously merging the changes.
Sends events on zmq channel, that can be read by any subscriber (typically the Qt app).

Profiling
=========
To obtain a useful callgraph with CPU usage:

```shell
python -m cProfile -o output.pstats main.py
# -n and -e followed by a number allow to set a limit for nodes and edges to be draw based on total % cpu
gprof2dot -e 0.01 -n 0.01 -f pstats output.pstats | dot -Tpng -o output001.png
```

Another interesting point is to add an **@profile** marker and use:
```shell
kernprof -v -l main.py
```

Profiling requires:
- graphviz (packet manager: port, brew, apt, pact, yum...)
- kernprof, gprof2dot, line_profiler (pip)
