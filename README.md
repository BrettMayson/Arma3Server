# Arma 3 Dedicated Server

[![Docker Pulls](https://img.shields.io/docker/pulls/synixebrett/arma3server.svg?style=flat-square)](https://hub.docker.com/r/synixebrett/arma3server)

An Arma 3 Dedicated Server. Updates to the latest version every time it is restarted.

## Usage

```
    docker create \
        --name=arma-server \
        -p 2302:2302/udp \
        -p 2303:2303/udp \
        -p 2304:2304/udp \
        -p 2305:2305/udp \
        -v path/to/missions:/arma3/mpmissions \
        -v path/to/configs:/arma3/configs \
        -v path/to/mods:/arma3/mods \
        -v path/to/servermods:/arma3/servermods \
        -e ARMA_CONFIG=main.cfg \
        -e STEAM_USER=myusername \
        -e STEAM_PASSWORD=mypassword \
        synixebrett/arma3server
```

Profiles are saved in `/arma3/configs/profiles`

## Parameters

| Parameter                     | Function                                                  | Default |
| -------------                 |--------------                                             | - |
| `-p 2302-2305`                | Ports required by Arma 3 |
| `-v /arma3/mpmission`         | Folder with MP Missions |
| `-v /arma3/configs`           | Folder containing config files |
| `-v /arma3/mods`              | Mods that will be loaded by clients |
| `-v /arma3/servermods`        | Mods that will only be loaded by the server |
| `-e PORT`                     | Port used by the server, (uses PORT to PORT+3)            | 2302 |
| `-e ARMA_BINARY`              | Arma 3 server binary to use, `./arma3server_x64` for x64   | `./arma3server` |
| `-e ARMA_CONFIG`              | Config file to load from `/arma3/configs`                 | `main.cfg` |
| `-e ARMA_PROFILE`             | Profile name, stored in `/arma3/configs/profiles`         | `main` |
| `-e ARMA_WORLD`               | World to load on startup                                  | `empty` |
| `-e ARMA_LIMITFPS`            | Maximum FPS | `1000` |
| `-e STEAM_BRANCH`             | Steam branch used by steamcmd | `public` |
| `-e STEAM_BRANCH_PASSWORD`    | Steam branch password used by steamcmd |
| `-e STEAM_USER`               | Steam username used to login to steamcmd |
| `-e STEAM_PASSWORD`           | Steam password |
| `-e HEADLESS_CLIENTS`         | Launch n number of headless clients                       | `0` |

The Steam account does not need to own Arma 3, but must have Steam Guard disabled.

List of Steam branches can be found on the Community Wiki, [Arma 3: Steam Branches](https://community.bistudio.com/wiki/Arma_3:_Steam_Branches)
