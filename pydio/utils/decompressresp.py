
import requests
import base64
import json
import zlib
import random

#r = requests.get("http://1:1@localhost:5556/feedbackinfo")
#res = json.loads(r.content)
f = open("filename", 'r')
res = f.read()
f.close()
dec64 = base64.b64decode(res["errors"])
#org = zlib.decompress(dec64[len("zlib_blob"):])
org = zlib.decompress(dec64)

res["errors"] = ""
print(json.dumps(res))

errs = eval(org)
print(len(errs))

for e in errs:
    if random.random() < .05:
        print(e)
