import os
import re
import shutil
import subprocess
from string import Template

import api
import local
import workshop

print("Starting Arma 3 Server...")

def mod_param(name, mods):
    return ' -{}="{}" '.format(name, ";".join(mods))

def env_defined(key):
    return key in os.environ and len(os.environ[key]) > 0

CONFIG_FILE = os.environ["ARMA_CONFIG"]
KEYS = "/arma3/server/keys"

if env_defined("CLEAR_KEYS") and os.environ["CLEAR_KEYS"] == "true" and os.path.isdir(KEYS):
    shutil.rmtree(KEYS)
if not os.path.isdir(KEYS):
    if os.path.exists(KEYS):
        os.remove(KEYS)
    os.makedirs(KEYS)

client = None
if os.environ["SKIP_INSTALL"] in ["", "false"]:
    client = api.login(os.environ["STEAM_USER"], os.environ["STEAM_PASSWORD"])
    if not client:
        print("Failed to login to Steam, exiting...")
        exit(1)
    api.download_depot(client, 233781) # Default Content
    api.download_depot(client, 233783) # Linux Server
    if os.environ["ARMA_BINARY"] == "arma3serverprofiling_x64":
        api.download_depot(client, 233785) # Arma 3 Profiling

    for cdlc in os.environ["ARMA_CDLC"].split(";"):
        if cdlc:
            cdlc = cdlc.lower()
            print("Downloading CDLC:", cdlc)
            api.download_depot(client, api.CDLC_IDS[cdlc])

# Mods

mods = []

if os.environ["MODS_PRESET"] != "":
    if not client:
        client = api.login(os.environ["STEAM_USER"], os.environ["STEAM_PASSWORD"])
    mods.extend(workshop.preset(os.environ["MODS_PRESET"], client))

if os.environ["MODS_LOCAL"] == "true" and os.path.exists("mods"):
    mods.extend(local.mods("mods"))

launch = "{} -limitFPS={} -world={} {} {}".format(
    os.environ["ARMA_BINARY"],
    os.environ["ARMA_LIMITFPS"],
    os.environ["ARMA_WORLD"],
    os.environ["ARMA_PARAMS"],
    mod_param("mod", mods),
)

if os.environ["ARMA_CDLC"] != "":
    for cdlc in os.environ["ARMA_CDLC"].split(";"):
        launch += " -mod={}".format(cdlc)

clients = int(os.environ["HEADLESS_CLIENTS"])
print("Headless Clients:", clients)

if clients != 0:
    with open("/arma3/server/configs/{}".format(CONFIG_FILE)) as config:
        data = config.read()
        regex = r"(.+?)(?:\s+)?=(?:\s+)?(.+?)(?:$|\/|;)"

        config_values = {}

        matches = re.finditer(regex, data, re.MULTILINE)
        for matchNum, match in enumerate(matches, start=1):
            config_values[match.group(1).lower()] = match.group(2)

        if "headlessclients[]" not in config_values:
            data += '\nheadlessclients[] = {"127.0.0.1"};\n'
        if "localclient[]" not in config_values:
            data += '\nlocalclient[] = {"127.0.0.1"};\n'

        with open("/tmp/arma3.cfg", "w") as tmp_config:
            tmp_config.write(data)
        launch += ' -config="/tmp/arma3.cfg"'

    client_launch = launch
    client_launch += " -client -connect=127.0.0.1 -port={}".format(os.environ["PORT"])
    if "password" in config_values:
        client_launch += " -password={}".format(config_values["password"])

    for i in range(0, clients):
        hc_template = Template(
            os.environ["HEADLESS_CLIENTS_PROFILE"]
        )  # eg. '$profile-hc-$i'
        hc_name = hc_template.substitute(
            profile=os.environ["ARMA_PROFILE"], i=i, ii=i + 1
        )

        hc_launch = client_launch + ' -name="{}"'.format(hc_name)
        print("LAUNCHING ARMA CLIENT {} WITH".format(i), hc_launch)
        subprocess.Popen(hc_launch, shell=True)

else:
    launch += ' -config="/arma3/server/configs/{}"'.format(CONFIG_FILE)

launch += ' -port={} -name="{}" -profiles="/arma3/server/configs/profiles"'.format(
    os.environ["PORT"], os.environ["ARMA_PROFILE"]
)

if os.path.exists("servermods"):
    launch += mod_param("serverMod", local.mods("servermods"))

print("LAUNCHING ARMA SERVER WITH", launch, flush=True)
os.chdir("/arma3/server")
os.system(launch)
