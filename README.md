# Arma 3 Dedicated Server

An Arma 3 Dedicated Server. Updates to the latest version every time it is restarted.

## Usage

```
    docker create \
        --name=arma-server \
        -p 2302:2302 \
        -p 2303:2303 \
        -p 2304:2304 \
        -p 2305:2305 \
        -v path/to/missions:/arma3/mpmissions \
        -v path/to/configs:/arma3/configs \
        -v path/to/mods:/arma3/mods \
        -v path/to/servermods:/arma3/servermods \
        -e ARMA_CONFIG=main.cfg
        -e STEAM_USERNAME=myusername
        -e STEAM_PASSWORD=mypassword
```

Profiles are saved in `/arma3/configs/profiles`

## Parameters

| Parameter      | Function | Default |
| -------------  |--------------| - |
| `-p 2302-2305` | Ports required by Arma 3 |
| `-v /arma3/mpmission`       | Folder with MP Missions      |
| `-v /arma3/configs` | Folder containing config files, used by `-e ARMA_CONFIG`|
| `-v /arma3/mods`  | Mods that will be loaded by clients      |
| `-v /arma3/servermods` | Mods that will only be loaded by the server |
| `-e ARMA_CONFIG` | Config file to load from `/arma3/configs` | `main.cfg` |
| `-e ARMA_PROFILE` | Profile name, profiles are stored in `/arma3/configs/profiles` | `main` |
| `-e ARMA_WORLD` | World to load on startup | `empty` |
| `-e STEAM_USERNAME` | Steam username used to login to steamcmd |
| `-e STEAM_PASSWORD` | Steam password |
The steam account does not need to own Arma 3, but must have Steam Guard disabled.
