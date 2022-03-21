import glob
import os
import shutil


def copy(moddir):
    keys = glob.glob(os.path.join(moddir, "**/*.bikey"))
    if len(keys) > 0:
        for key in keys:
            if not os.path.isdir(key):
                shutil.copy2(key, "/arma3/keys")
    else:
        print("Missing keys:", moddir)


if __name__ == "__main__":
    for moddir in glob.glob("/arma3/steamapps/workshop/content/107410/*"):
        copy(moddir)
