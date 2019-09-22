import subprocess
import os
import shutil

subprocess.call(["/steamcmd/steamcmd.sh", "+login", os.environ["STEAM_USER"], os.environ["STEAM_PASSWORD"], "+force_install_dir", "/arma3", "+app_update", "233780", "validate", "+quit"])

def mods(d):
    launch = "\""
    mods = [os.path.join(d,o) for o in os.listdir(d) if os.path.isdir(os.path.join(d,o))]
    for m in mods:
        launch += m+";"
        keysdir = os.path.join(m,"keys")
        if os.path.exists(keysdir):
            keys = [os.path.join(keysdir,o) for o in os.listdir(keysdir) if os.path.isdir(os.path.join(keysdir,o)) == False]
            for k in keys:
                shutil.copy2(k, "/arma3/keys")
        else:
            print("Missing keys:", keysdir)
    return launch+"\""

launch = "/arma3/arma3server -config=\"/arma3/configs/{}\" -profiles=\"/arma3/configs/profiles\" -name=\"{}\" -mod={} -world={}".format(os.environ["ARMA_CONFIG"], os.environ["ARMA_PROFILE"], mods('mods'), os.environ["ARMA_WORLD"])

if str(os.environ["HEADLESS"]) == "true":
    launch += " -client -connect={} -password={}".format(os.environ["HEADLESS_SERVER"], os.environ["HEADLESS_PASSWORD"])
else:
    launch += " -servermod={}".format(mods('servermods'))

print("LAUNCHING ARMA SERVER WITH",launch)
os.system(launch)
