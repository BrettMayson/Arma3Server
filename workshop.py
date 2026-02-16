import os
import re
import subprocess
import urllib.request
import shutil
from urllib.parse import urlparse
import smbclient
from smbclient import ClientConfig

import keys
import api

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"  # noqa: E501

def preset(mod_file, client):
    if mod_file.startswith("http"):
        req = urllib.request.Request(
            mod_file,
            headers={"User-Agent": USER_AGENT},
        )
        remote = urllib.request.urlopen(req)
        with open("preset.html", "wb") as f:
            f.write(remote.read())
        mod_file = "preset.html"
    elif mod_file.startswith("smb://"):
        # Parse SMB URL and setup anonymous/guest connection
        parsed = urlparse(mod_file)
        server = parsed.hostname
        # Configure client to disable encryption and signing for guest access
        ClientConfig(require_signing=False, require_encryption=False)
        # Register guest session for anonymous access
        smbclient.register_session(server, username='guest', password='')
        
        with smbclient.open_file(mod_file, mode='rb') as remote:
            with open("preset.html", "wb") as f:
                f.write(remote.read())
        mod_file = "preset.html"
    mods = []
    moddirs = []
    with open(mod_file) as f:
        html = f.read()
        regex = r"filedetails\/\?id=(\d+)\""
        matches = re.finditer(regex, html, re.MULTILINE)
        for _, match in enumerate(matches, start=1):
            mods.append(match.group(1))
            api.download_workshop(client, int(match.group(1)))
            moddirs.append("workshop/" + match.group(1))
        for moddir in moddirs:
            keys.copy("server/"+moddir)
    return moddirs
