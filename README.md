pydio-sync
==========

New Python version of the Pydio synchronization client [work in progress]

This is a python rewrite of the current java-based synchro client. The work is still in progress and requires a couple of stuff to be deployed on the server-side to work. 

Server Setup
--
Pydio server needs the following to be turned on:
 * *RESTfull access* point (see /rest.php file) and a working pair of credentials for that (rest_user/rest_password)
 * *DB-based setup* : serial-based will soon be deprecated anyway
 * *Meta.syncable plugin* applied to the workspace you want to synchronize. This will track all the changes in a specific db-table, making it very quick for the sync client to load the last changes.
 * *php_rsync* extension on the server to allow transferring files deltas instead of complete files contents when modified. Not yet implemented but will be back at one point.

Client Setup
-- 
 * Make sure to install Python 2.7
 * Install Zero MQ on the client (see http://zeromq.org/area:download)
 * Install pip
 * Run: ```pip install git+https://github.com/pydio/pydio-sync.git```
 * Start main module with the following parameters: ```python -m pydio.main --server=http://yourserver --directory=/path/to/local/dir --workspace=workspace-alias --user=rest_user --password=rest_password```

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
