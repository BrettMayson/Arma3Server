import os
import shutil


def copy_keys(moddir):
    keysdir = os.path.join(moddir, "keys")
    if os.path.exists(keysdir):
        for o in os.listdir(keysdir):
            keyfile = os.path.join(keysdir, o)
            if not os.path.isdir(keyfile):
                shutil.copy2(keyfile, "/arma3/keys")
    else:
        print("Missing keys:", keysdir)


def mods(d):
    mods = []

    # Find mod folders
    for m in os.listdir(d):
        moddir = os.path.join(d, m)
        if os.path.isdir(moddir):
            mods.append(moddir)
            copy_keys(moddir)

    return mods
