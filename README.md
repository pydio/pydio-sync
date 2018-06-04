pydio-sync
==========

New Python version of the Pydio synchronization client [beta]

The work is still in progress. Make sure your server is recent and properly configured. This https://pydio.com/en/docs/v8/checking-sync can help.

This is a python rewrite of the former java-based synchro client.

## Server Requirements
Pydio server needs the following to be turned on:
 * *RESTfull access* point (see /rest.php file) and a working pair of credentials for that (rest_user/rest_password)
 * *DB-based setup* : serial-based will soon be deprecated anyway
 * *Meta.syncable plugin* applied to the workspace you want to synchronize. This will track all the changes in a specific db-table, making it very quick for the sync client to load the last changes.
 * *php_rsync* extension on the server to allow transferring files deltas instead of complete files contents when modified. Not yet implemented but will be back at one point.

##Client Setup

### Installing

 * Make sure to install [Python](https://www.python.org/) 2.7
 * Install [pip](https://pypi.python.org/pypi/pip) - Make sure to have a version 1.4 or upper on Linux
 * Run: ```pip install git+https://github.com/pydio/pydio-sync.git```

### Quick start
Start main module
```
python -m pydio.main
```
If the UI is not installed, simply launched your webbrowser at [http://127.0.0.1:5556/](http://127.0.0.1:5556/), you can now create a synchronisation task. Your data will be stored in *USER_HOME/.pydio_data/*

Start with non-random credentials for the web-UI:
```
python -m pydio.main --api_user=UsernameForTheWebInterface --api_password=PasswordForTheWebInterface
```

### Alternative parameters

Alternatively, you can start the program with the following parameters:
 * Pass a server configuration through parameters (will be added to the config file)
```
python -m pydio.main 
        --server=http://yourserver 
        --directory=/path/to/local/dir 
        --workspace=workspace-alias 
        --user=rest_user 
        --password=rest_password
```
 * Pass a path to a json file containing the server configs: 
```
python -m pydio.main 
        --file=/path/to/config.json
```
In that case, the JSON file must contain an array of "jobs configs" objects, including a __type__ key with value "JobConfig":
```
[
    {
        "__type__"  : "JobConfig", // This one is important!
        "server"    : "http://mydomain.tld/path",
        "workspace" : "ws_alias_or_id",
        "directory" : "/Path/to/local/folder",
        "user"      : "user",
        "password"  : "password",
        "direction" : "bi", // can be "up", "down", "bi"
        "active"    : true
    }
]
```

## Development Setup

### Linux

```
sudo apt-get install python
sudo apt-get install python-dev
sudo apt-get install python-pip
sudo apt-get install libzmq3-dev
```

### Windows

Install [python 2.7](https://www.python.org/download/releases/2.7/).
To quickly setup python start powershell and paste this script

    (new-object System.Net.WebClient).DownloadFile("https://www.python.org/ftp/python/2.7.6/python-2.7.6.msi", "$pwd\python-2.7.6.msi"); msiexec /i python-2.7.6.msi TARGETDIR=C:\Python27
    [Environment]::SetEnvironmentVariable("Path", "$env:Path;C:\Python27\;C:\Python27\Scripts\", "User")

Install [Pip](http://pip.readthedocs.org/en/latest/installing.html) using powershell

    (new-object System.Net.WebClient).DownloadFile("https://raw.github.com/pypa/pip/master/contrib/get-pip.py", "$pwd\get-pip.py"); C:\Python27\python.exe get-pip.py virtualenv

or using python itself

    python -c "exec('try: from urllib2 import urlopen \nexcept: from urllib.request import urlopen');f=urlopen('https://raw.github.com/pypa/pip/master/contrib/get-pip.py').read();exec(f)"

Run sandbox.py to create virtual environment and build the app

### All platforms
```
mkvirtualenv pydioenv
source pydioenv/bin/activate
pip install -r requirements.txt
# do some changes
python main.py
```

## Profiling
```
python -m pydio.main -mp True
```

or

Profiling requires:
- graphviz (packet manager: port, brew, apt, pact, yum...)
- kernprof, gprof2dot, line_profiler (pip)

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

## Reporting Issues

If you have any questions, please consider finding or posting them on our <a href="https://pydio.com/forum/f/forum/troubleshooting/pydiosync/">dedicated forum</a>, once it is qualified as a bug, you can open issues.

## Contributing

Please <a href="http://pyd.io/contribute/cla">sign the Contributor License Agreement</a> before contributing.
