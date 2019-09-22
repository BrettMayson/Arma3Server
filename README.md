# Arma 3 Dedicated Server

[![Docker Pulls](https://img.shields.io/docker/pulls/synixebrett/arma3server.svg?style=flat-square)](https://hub.docker.com/r/synixebrett/arma3server)

An Arma 3 Dedicated Server. Updates to the latest version every time it is restarted.

## Usage

```
    docker create \
        --name=arma-server \
        -p 2302:2302 \
        -p 2303:2303 \
        -p 2304:2304 \
        -p 2305:2305 \
        -v path/to/missions:/mpmissions \
        -v path/to/configs:/configs \
        -v path/to/mods:/mods \
        -v path/to/servermods:/servermods \
        -e ARMA_CONFIG=main.cfg \
        -e STEAM_USERNAME=myusername \
        -e STEAM_PASSWORD=mypassword \
        synixebrett/arma3server
```

Profiles are saved in `/configs/profiles`

## Parameters

| Parameter             | Function | Default |
| -------------         |--------------| - |
| `-p 2302-2305`        | Ports required by Arma 3 |
| `-v /mpmission`       | Folder with MP Missions |
| `-v /configs`         | Folder containing config files |
| `-v /mods`            | Mods that will be loaded by clients |
| `-v /servermods`      | Mods that will only be loaded by the server |
| `-e ARMA_CONFIG`      | Config file to load from `/configs`               | `main.cfg` |
| `-e ARMA_PROFILE`     | Profile name, stored in `/configs/profiles`       | `main` |
| `-e ARMA_WORLD`       | World to load on startup                          | `empty` |
| `-e STEAM_USERNAME`   | Steam username used to login to steamcmd |
| `-e STEAM_PASSWORD`   | Steam password |
| `-e HEADLESS_CLIENTS` | Launch n number of headless clients               | `0` |

The Steam account does not need to own Arma 3, but must have Steam Guard disabled.
