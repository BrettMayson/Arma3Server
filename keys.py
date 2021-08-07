import os
import shutil


def copy(moddir):
    keysdir = os.path.join(moddir, "keys")
    if os.path.exists(keysdir):
        for o in os.listdir(keysdir):
            keyfile = os.path.join(keysdir, o)
            if not os.path.isdir(keyfile):
                shutil.copy2(keyfile, "/arma3/keys")
    else:
        print("Missing keys:", keysdir)
