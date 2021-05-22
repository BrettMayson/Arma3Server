import subprocess
import os
import shutil
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
import socket
import boto3
import multiprocessing
import zipfile
import time

CONFIG_FILE = os.environ["ARMA_CONFIG"]
KEYS = "/arma3/keys"
DATA_BUCKET = os.environ["DATA_BUCKET"]

def reset_keys_folder():
    if not os.path.exists(KEYS) or not os.path.isdir(KEYS):
        if os.path.exists(KEYS):
            os.remove(KEYS)
        os.makedirs(KEYS)

def run_healthcheck_server():
    host = ''        # Symbolic name meaning all available interfaces
    port = 12345     # Arbitrary non-privileged port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, port))
    while True:
        s.listen(1)
        conn, addr = s.accept()
        print('Connected by', addr)
        conn.sendall("healthy".encode())
        conn.close()
        print('Closed connection', addr)

def init_steamcmd():
    steamcmd = ["/steamcmd/steamcmd.sh"]
    steamcmd.extend(["+login", os.environ["STEAM_USER"], os.environ["STEAM_PASSWORD"]])
    steamcmd.extend(["+force_install_dir", "/arma3"])
    steamcmd.extend(["+app_update", "233780"])
    if "STEAM_BRANCH" in os.environ and len(os.environ["STEAM_BRANCH"]) > 0:
        steamcmd.extend(["-beta", os.environ["STEAM_BRANCH"]])
    if "STEAM_BRANCH_PASSWORD" in os.environ and len(os.environ["STEAM_BRANCH_PASSWORD"]) > 0:
        steamcmd.extend(["-betapassword", os.environ["STEAM_BRANCH_PASSWORD"]])
    steamcmd.extend(["validate", "+quit"])
    subprocess.call(steamcmd)

def build_mods_string(d):
    launch = "\""
    mods = [os.path.join(d,o) for o in os.listdir(d) if os.path.isdir(os.path.join(d,o))]
    for m in mods:
        launch += m+";"
        keysdir = os.path.join(m,"keys")
        if os.path.exists(keysdir):
            keys = [os.path.join(keysdir,o) for o in os.listdir(keysdir) if os.path.isdir(os.path.join(keysdir,o)) == False]
            for k in keys:
                shutil.copy2(k, KEYS)
        else:
            print("Missing keys:", keysdir)
    return launch+"\""

def download_data():
    s3 = boto3.client('s3')
    s3.download_file(DATA_BUCKET, "mods.zip", "mods.zip")
    with zipfile.ZipFile("mods.zip", 'r') as zip_ref:
        zip_ref.extractall("/arma3/mods")

############################################################################################################################

healthcheck_process = multiprocessing.Process(target=run_healthcheck_server)
healthcheck_process.start()

reset_keys_folder()
init_steamcmd()

launch = "{} -limitFPS={} -world={}".format(os.environ["ARMA_BINARY"], os.environ["ARMA_LIMITFPS"], os.environ["ARMA_WORLD"])

if os.path.exists("mods"):
    launch += " -mod={}".format(build_mods_string("mods"))

launch += " -config=\"/arma3/configs/{}\"".format(CONFIG_FILE)
launch += " -port={} -name=\"{}\" -profiles=\"/arma3/configs/profiles\"".format(os.environ["PORT"], os.environ["ARMA_PROFILE"])

if os.path.exists("servermods"):
    launch += " -serverMod={}".format(build_mods_string("servermods"))

print("LAUNCHING ARMA SERVER WITH", launch, flush=True)
os.system(launch)
healthcheck_process.terminate()
