pydio-sync
==========

New Python version of the Pydio synchronization client [pre-alpha]

This is a python rewrite of the current java-based synchro client. The work is still in progress and requires a couple of stuff to be deployed on the server-side to work. 

## Server Requirements
Pydio server needs the following to be turned on:
 * *RESTfull access* point (see /rest.php file) and a working pair of credentials for that (rest_user/rest_password)
 * *DB-based setup* : serial-based will soon be deprecated anyway
 * *Meta.syncable plugin* applied to the workspace you want to synchronize. This will track all the changes in a specific db-table, making it very quick for the sync client to load the last changes.
 * *php_rsync* extension on the server to allow transferring files deltas instead of complete files contents when modified. Not yet implemented but will be back at one point.

##Client Setup

### Installing

 * Make sure to install Python 2.7
 * Install pip - Make sure to have a version 1.4 or upper on Linux
 * Run: ```pip install git+https://github.com/pydio/pydio-sync.git```

### Quick start
Start main module
```
python -m pydio.main
```
If the UI is not installed, simply launched your webbrowser at http://127.0.0.1:5556/, you can now create a synchronisation task. Your data will be stored in USER_HOME/.pydio_data/

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


## Contributing

Please <a href="http://pyd.io/contribute/cla">sign the Contributor License Agreement</a> before contributing.
