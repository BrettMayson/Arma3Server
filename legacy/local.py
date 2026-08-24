import os

import keys


def mods(d):
    mods = []

    # Find mod folders
    for m in os.listdir(d):
        moddir = os.path.join(d, m)
        if os.path.isdir(moddir):
            mods.append(moddir)
            keys.copy(moddir)

    return mods
