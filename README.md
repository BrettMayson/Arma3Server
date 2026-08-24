# Arma 3 Dedicated Server

An Arma 3 Dedicated Server. Updates to the latest version every time it is restarted.

## Usage

### Docker CLI

```s
    docker create \
        --name=arma-server \
        -p 2302:2302/udp \
        -p 2303:2303/udp \
        -p 2304:2304/udp \
        -p 2305:2305/udp \
        -p 2306:2306/udp \
        -v path/to/missions:/arma3/server/mpmissions \
        -v path/to/configs:/arma3/server/configs \
        -v path/to/mods:/arma3/server/mods \
        -v path/to/servermods:/arma3/server/servermods \
        -e ARMA3_STEAM__USER=myusername \
        -e ARMA3_STEAM__PASSWORD=mypassword \
        ghcr.io/brettmayson/arma3server/arma3server:v2
```

The server is a single Rust binary (`arma3server`) that installs/updates itself via Steam (using [steamroom](https://github.com/landaire/steamroom)) and launches the Arma 3 process. Legacy Python scripts are kept under [legacy/](legacy/) for reference only and are not used at runtime.

### docker-compose

Use the docker-compose.yml file inside a folder. It will automatically create 4 folders in which the missions, configs, mods and servermods can be loaded.

Copy the `.env.example` file to `.env`, containing at least `ARMA3_STEAM__USER` and `ARMA3_STEAM__PASSWORD`.

All settings can also be supplied via an optional `config.toml` mounted at `/arma3/config.toml` (override the path with `ARMA3_CONFIG_FILE`). Environment variables always take priority over the TOML file. See [Configuration](#configuration) below for the TOML layout.

Use `docker-compose start` to start the server.

Use `docker-compose logs` to see server logs.

Use `docker-compose down` to shutdown the server.

The `network_mode: host` can be changed to explicit ports if needed.

Use `docker-compose up -d` to start the server, detached.

See [Docker-compose](https://docs.docker.com/compose/install/#install-compose) for an installation guide.

Profiles are saved in `/arma3/server/configs/profiles`

## Parameters

| Parameter                     | Function                                                  | Default |
| -------------                 |--------------                                             | - |
| `-p 2302-2306`                | Ports required by Arma 3 |
| `-v /arma3/server/mpmission`         | Folder with MP Missions |
| `-v /arma3/server/configs`           | Folder containing config files |
| `-v /arma3/server/mods`              | Mods that will be loaded by clients |
| `-v /arma3/server/servermods`        | Mods that will only be loaded by the server |
| `-v /arma3/server`        | Folder containing the server files |
| `-e PORT`                     | Port used by the server, (uses PORT to PORT+3)            | 2302 |
| `-e ARMA3_SERVER__BINARY`     | Arma 3 server binary to use   | `./arma3server_x64` |
| `-e ARMA3_SERVER__CONFIG`     | Config file to load from `/arma3/server/configs`                 | `main.cfg` |
| `-e ARMA3_SERVER__PARAMS`     | Additional Arma CLI parameters |
| `-e ARMA3_SERVER__PROFILE`    | Profile name, stored in `/arma3/server/configs/profiles`         | `main` |
| `-e ARMA3_SERVER__WORLD`      | World to load on startup                                  | `empty` |
| `-e ARMA3_SERVER__LIMIT_FPS`  | Maximum FPS | `1000` |
| `-e ARMA3_SERVER__CDLC`       | cDLCs to load, separated by commas                        | - |
| `-e ARMA3_STEAM__USER`        | Steam username used to login |
| `-e ARMA3_STEAM__PASSWORD`    | Steam password |
| `-e ARMA3_HEADLESS__CLIENTS`  | Launch n number of headless clients                       | `0` |
| `-e ARMA3_HEADLESS__PROFILE`  | Headless client profile name (supports placeholders)      | `$profile-hc-$i` |
| `-e ARMA3_MODS__LOCAL`        | Should the mods folder be loaded | `true` |
| `-e ARMA3_MODS__PRESET`       | An Arma 3 Launcher preset to load |
| `-e ARMA3_SERVER__SKIP_INSTALL` | Skip Arma 3 installation | `false` |
| `-e ARMA3_SERVER__CLEAR_KEYS` | Clear the keys directory every launch (keys will still be copied from mods) | `true` |
| `-e ARMA3_CONFIG_FILE`        | Path to an optional `config.toml` with default values | `/arma3/config.toml` |

The Steam account does not need to own Arma 3, but must have Steam Guard disabled.

List of Steam branches can be found on the Community Wiki, [Arma 3: Steam Branches](https://community.bistudio.com/wiki/Arma_3:_Steam_Branches)

## Configuration

Instead of (or alongside) environment variables, settings can be provided in a `config.toml` mounted at `/arma3/config.toml`. Environment variables always override matching TOML values.

```toml
cdlc = ["csla", "gm"]

[steam]
user = "myusername"
password = "mypassword"
branch = "public"

[server]
binary = "./arma3server_x64"
config = "main.cfg"
profile = "main"
world = "empty"
limit_fps = 1000
port = 2302
skip_install = false
clear_keys = true

[mods]
local = true
preset = ""

[headless]
clients = 0
profile = "$profile-hc-$i"
```

## Creator DLC

You do not need to be on the `creatordlc` branch to use a CDLC. Using that branch will download all the CDLCs, but you can also use the `public` branch and specify which CDLCs to load with the `ARMA3_SERVER__CDLC` environment variable. Only the specified CDLCs will be downloaded and loaded by the server.

| Name | Flag |
| ---- | ---- |
| [CSLA Iron Curtain](https://store.steampowered.com/app/1294440/Arma_3_Creator_DLC_CSLA_Iron_Curtain/) | csla |
| [Global Mobilization - Cold War Germany](https://store.steampowered.com/app/1042220/Arma_3_Creator_DLC_Global_Mobilization__Cold_War_Germany/) | gm |
| [S.O.G. Prairie Fire](https://store.steampowered.com/app/1227700/Arma_3_Creator_DLC_SOG_Prairie_Fire) | vn |
| [Western Sahara](https://store.steampowered.com/app/1681170/Arma_3_Creator_DLC_Western_Sahara/) | ws |
| [Spearhead 1944](https://store.steampowered.com/app/1175380/Arma_3_Creator_DLC_Spearhead_1944/) | spe |
| [Reaction Forces](https://store.steampowered.com/app/2647760/Arma_3_Creator_DLC_Reaction_Forces/) | rf |
| [Expeditionary Forces](https://store.steampowered.com/app/2647830/Arma_3_Creator_DLC_Expeditionary_Forces/) | ef |

Bohemia-updated list of codes here: <https://community.bistudio.com/wiki/Category:Arma_3:_CDLCs>

### Example

`-e ARMA3_SERVER__CDLC="csla,gm,vn,ws,spe"`

## Loading mods

### Local

1. Place the mods inside `/mods` or `/servermods`.
2. Be sure that the mod folder is all lowercase and does not show up with quotation marks around it when listing the directory eg `'@ACE(v2)'`
3. Run the following command from the mods and/or servermods directory to confirm that all the files are lowercase.
    `find . -depth -exec rename 's/(.*)\/([^\/]*)/$1\/\L$2/' {} \;`
    If this is NOT the case, the mods will prevent the server from booting.
4. Make sure that each mod contains a lowercase `/addons` folder. This folder also needs to be lowercase in order for the server to load the required PBO files inside.
5. Start the server.

### Workshop

Set the environment variable `ARMA3_MODS__PRESET` to the HTML preset file exported from the Arma 3 Launcher. The path can be local file or a URL. A volume can be created at `/arma3/server/workshop/` to preserve the mods between containers separately from the main `/arma3/server` volume.

`-e ARMA3_MODS__PRESET="my_mods.html"`

`-e ARMA3_MODS__PRESET="http://example.com/my_mods.html"`
