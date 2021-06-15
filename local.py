import os
import shutil

def scan(d):
    mods = []
    scan = [os.path.join(d,o) for o in os.listdir(d) if os.path.isdir(os.path.join(d,o))]
    for m in scan:
        mods.append(m)
        keysdir = os.path.join(m,"keys")
        if os.path.exists(keysdir):
            keys = [os.path.join(keysdir,o) for o in os.listdir(keysdir) if os.path.isdir(os.path.join(keysdir,o)) == False]
            for k in keys:
                shutil.copy2(k, "/arma3/keys")
        else:
            print("Missing keys:", keysdir)
    return mods
