import os, subprocess

LOCAL = "/arma3/mods/"
WORKSHOP = "/arma3/steamapps/workshop/content/107410/"

def mod(id):
    steamcmd = ["/steamcmd/steamcmd.sh"]
    steamcmd.extend(["+login", os.environ["STEAM_USER"], os.environ["STEAM_PASSWORD"]])
    steamcmd.extend(["+force_install_dir", "/arma3"])
    steamcmd.extend(["+workshop_download_item", "107410", id])
    steamcmd.extend(["+quit"])
    subprocess.call(steamcmd)

def preset(mod_file):
    if mod_file.startswith("http"):
        import urllib.request
        req = urllib.request.Request(
            mod_file,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
            }
        )
        remote = urllib.request.urlopen(req)
        with open("preset.html", 'wb') as f:
            f.write(remote.read())
        mod_file = "preset.html"
    mods = []
    with open(mod_file) as f:
        html = f.read()
        import re
        regex = r"filedetails\/\?id=(\d+)\""
        matches = re.finditer(regex, html, re.MULTILINE)
        for _, match in enumerate(matches, start=1):
            mod(match.group(1))
            mods.append(WORKSHOP + match.group(1))
    return mods
