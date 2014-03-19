python
======

Sync daemon listening for both local folder and server changes and continuously merging the changes.
Sends events on zmq channel, that can be read by any subscriber (typically the Qt app).
