import subprocess
import os
import shutil
import re

CONFIG_FILE = os.environ["ARMA_CONFIG"]

subprocess.call(["/home/steam/steamcmd/steamcmd.sh", "+login", os.environ["STEAM_USER"], os.environ["STEAM_PASSWORD"], "+force_install_dir", "/home/steam/arma3", "+app_update", "233780", "validate", "+quit"])

def mods(d):
    launch = "\""
    mods = [os.path.join(d,o) for o in os.listdir(d) if os.path.isdir(os.path.join(d,o))]
    for m in mods:
        launch += m+";"
        keysdir = os.path.join(m,"keys")
        if os.path.exists(keysdir):
            keys = [os.path.join(keysdir,o) for o in os.listdir(keysdir) if os.path.isdir(os.path.join(keysdir,o)) == False]
            for k in keys:
                shutil.copy2(k, "/home/steam/arma3/keys")
        else:
            print("Missing keys:", keysdir)
    return launch+"\""

launch = "/home/steam/arma3/arma3server  -profiles=\"/configs/profiles\" -name=\"{}\" -mod={} -world={}".format(os.environ["ARMA_PROFILE"], mods('mods'), os.environ["ARMA_WORLD"])

clients = int(os.environ["HEADLESS_CLIENTS"])

print("Headless Clients:", clients)

if clients != 0:
    with open("/configs/{}".format(CONFIG_FILE)) as config:
        data = config.read()
        regex = r"(.+?)(?:\s+)?=(?:\s+)?(.+?)(?:$|\/|;)"

        config_values = {}

        matches = re.finditer(regex, data, re.MULTILINE)
        for matchNum, match in enumerate(matches, start=1):
            config_values[match.group(1).lower()] = match.group(2)

        print("Config: ", config_values)

        if not "headlessclients[]" in config_values:
            config_values["headlessclients[]"] = "{\"127.0.0.1\"}"
        if not "localclient[]" in config_values:
            config_values["localclient[]"] = "{\"127.0.0.1\"}"

        with open("/tmp/arma3.cfg", "w") as tmp_config:
            for key, value in config_values.items():
                tmp_config.write("{} = {};\n".format(key, value))
        launch += " -config=\"/tmp/arma3.cfg\""

    
    client_launch = launch
    client_launch += " -client -connect=127.0.0.1"
    if "password" in config_values:
        client_launch += " -password={}".format(config_values["password"])

    for i in range(0, clients):
        print("LAUNCHING ARMA CLIENT {} WITH".format(i), client_launch)
        subprocess.Popen(client_launch, shell=True)

else:
    launch += " -config=\"/configs/{}\"".format(CONFIG_FILE)

launch += " -serverMod={}".format(mods('servermods'))

print("LAUNCHING ARMA SERVER WITH",launch)
os.system(launch)
