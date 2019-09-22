#!/bin/bash

# Allow us to debug what's happening in the script if necessary
if [ "$STEAM_DEBUG" ]; then
	set -x
fi
export TEXTDOMAIN=steam
export TEXTDOMAINDIR=/usr/share/locale

# figure out the absolute path to the script being run a bit
# non-obvious, the ${0%/*} pulls the path out of $0, cd's into the
# specified directory, then uses $PWD to figure out where that
# directory lives - and all this in a subshell, so we don't affect
# $PWD

STEAMROOT="$(cd "${0%/*}" && echo $PWD)"
STEAMDATA="$STEAMROOT"
if [ -z $STEAMEXE ]; then
  STEAMEXE=`basename "$0" .sh`
fi
# Backward compatibility for server operators
if [ "$STEAMEXE" = "steamcmd" ]; then
	echo "***************************************************"
	echo "The recommended way to run steamcmd is: steamcmd.sh $*"
	echo "***************************************************"
	exec "$STEAMROOT/steamcmd.sh" "$@"
	echo "Couldn't find steamcmd.sh" >&1
	exit 255
fi
cd "$STEAMROOT"

# The minimum version of the /usr/bin/steam script that we require
MINIMUM_STEAMSCRIPT_VERSION=100020

# Save the system paths in case we need to restore them
export SYSTEM_PATH="$PATH"
export SYSTEM_LD_LIBRARY_PATH="$LD_LIBRARY_PATH"

function show_message()
{
	style=$1
	shift
	if ! zenity "$style" --text="$*" 2>/dev/null; then
		case "$style" in
		--error)
			title=$"Error"
			;;
		--warning)
			title=$"Warning"
			;;
		*)
			title=$"Note"
			;;
		esac

		# Save the prompt in a temporary file because it can have newlines in it
		tmpfile="$(mktemp || echo "/tmp/steam_message.txt")"
		echo -e "$*" >"$tmpfile"
		xterm -T "$title" -e "cat $tmpfile; echo -n 'Press enter to continue: '; read input" 2>/dev/null || \
			(echo "$title:"; cat "$tmpfile"; echo -n 'Press enter to continue: '; read input)
		rm -f "$tmpfile"
	fi
}

function warn_outofdate()
{
	show_message --warning $"Your steam package is out of date. Please get an updated version from your package provider or directly from http://repo.steampowered.com/steam for supported distributions."
}

function distro_description()
{
	echo "$(detect_distro) $(detect_release) $(detect_arch)"
}

function detect_distro()
{
	if [ -f /etc/lsb-release ]; then
		(. /etc/lsb-release; echo $DISTRIB_ID | tr '[A-Z]' '[a-z]')
	elif [ -f /etc/os-release ]; then
		(. /etc/os-release; echo $ID | tr '[A-Z]' '[a-z]')
	else
		# Generic fallback
		uname -s
	fi
}

function detect_release()
{
	if [ -f /etc/lsb-release ]; then
		(. /etc/lsb-release; echo $DISTRIB_RELEASE)
	elif [ -f /etc/os-release ]; then
		(. /etc/os-release; echo $VERSION_ID)
	else
		# Generic fallback
		uname -r
	fi
}

function detect_arch()
{
	case $(uname -m) in
	*64)
		echo "64-bit"
		;;
	*)
		echo "32-bit"
		;;
	esac
}

function detect_platform()
{
	# Default to unknown/unsupported distribution, pick something and hope for the best
	platform=ubuntu12_32

	# Check for specific supported distribution releases
	case "$(detect_distro)-$(detect_release)" in
	ubuntu-12.*)
		platform=ubuntu12_32
		;;
	esac
	echo $platform
}

function detect_universe()
{
	if test -f "$STEAMROOT/Steam.cfg" && \
	     egrep '^[Uu]niverse *= *[Bb]eta$' "$STEAMROOT/Steam.cfg" >/dev/null; then
		STEAMUNIVERSE="Beta"
	elif test -f "$STEAMROOT/steam.cfg" && \
	     egrep '^[Uu]niverse *= *[Bb]eta$' "$STEAMROOT/steam.cfg" >/dev/null; then
		STEAMUNIVERSE="Beta"
	else
		STEAMUNIVERSE="Public"
	fi
	echo $STEAMUNIVERSE
}

function detect_package()
{
	case `detect_universe` in
	"Beta")
		STEAMPACKAGE="steambeta"
		;;
	*)
		STEAMPACKAGE="steam"
		;;
	esac
	echo "$STEAMPACKAGE"
}

function detect_scriptversion()
{
	SCRIPT_VERSION=$(fgrep "$2=" "$1")
	if [[ "$SCRIPT_VERSION" ]]; then
		expr "$SCRIPT_VERSION" : ".*=\(.*\)"
	else
		echo "0"
	fi
}

# Check a currently installed script against a new script and see if the
# installed one needs to be updated.
function check_scriptversion()
{
	SCRIPT=$1
	VERSION_TOKEN=$2
	MINIMUM_VERSION=$3

	VERSION="$(detect_scriptversion "$SCRIPT" $VERSION_TOKEN)"
	if [[ "$VERSION" -lt "$MINIMUM_VERSION" ]]; then
		return 1
	fi
	return 0
}

function detect_steamdatalink()
{
	# Don't create a link in development
	if [ -f "$STEAMROOT/steam_dev.cfg" ]; then
		STEAMDATALINK=""
	else
		STEAMDATALINK="$STEAMCONFIG/`detect_package`"
	fi
	echo $STEAMDATALINK
}

function detect_bootstrap()
{
	if [ -f "$STEAMROOT/bootstrap.tar.xz" ]; then
		echo "$STEAMROOT/bootstrap.tar.xz"
	else
		# This is the default bootstrap install location for the Ubuntu package.
		# We use this as a fallback for people who have an existing installation and have never run the new install_bootstrap code in bin_steam.sh
		echo "/usr/lib/`detect_package`/bootstraplinux_`detect_platform`.tar.xz"
	fi
}

function install_bootstrap()
{
	# Don't install bootstrap in development
	if [ -f "$STEAMROOT/steam_dev.cfg" ]; then
		return 1
	fi

	STATUS=0

	# Save the umask and set strong permissions
	omask=`umask`
	umask 0077

	STEAMBOOTSTRAPARCHIVE=`detect_bootstrap`
	if [ -f "$STEAMBOOTSTRAPARCHIVE" ]; then
		echo "Installing bootstrap $STEAMBOOTSTRAPARCHIVE"
		tar xf "$STEAMBOOTSTRAPARCHIVE"
		STATUS=$?
	else
		show_message --error $"Couldn't start bootstrap and couldn't reinstall from $STEAMBOOTSTRAPARCHIVE.  Please contact technical support."
		STATUS=1
	fi

	# Restore the umask
	umask $omask

	return $STATUS
}

function runtime_supported()
{
	case "$(detect_distro)-$(detect_release)" in
	# Add additional supported distributions here
	ubuntu-*)
		return 0
		;;
	*)	# Let's try this out for now and see if it works...
		return 0
		;;
	esac

	# This distro doesn't support the Steam Linux Runtime (yet!)
	return 1
}

function has_runtime_archive()
{
	# Make sure we have files to unpack
	for file in "$STEAM_RUNTIME".tar.bz2*; do
		if [ ! -f "$file" ]; then
			return 1
		fi
	done

	if [ ! -f "$STEAM_RUNTIME.checksum" ]; then
		return 1
	fi

	return 0
}

function unpack_runtime()
{
	if ! has_runtime_archive; then
		if [ -d "$STEAM_RUNTIME" ]; then
			# The runtime is unpacked, let's use it!
			return 0
		fi
		return 1
	fi

	# Make sure we haven't already unpacked them
	if [ -f "$STEAM_RUNTIME/checksum" ] && cmp "$STEAM_RUNTIME.checksum" "$STEAM_RUNTIME/checksum" >/dev/null; then
		return 0
	fi

	# Unpack the runtime
	EXTRACT_TMP="$STEAM_RUNTIME.tmp"
	rm -rf "$EXTRACT_TMP"
	mkdir "$EXTRACT_TMP"
	if ! (cd "$EXTRACT_TMP" && cat "$STEAM_RUNTIME".tar.bz2* | tar xjf -); then
		return 2
	fi

	# Move it into place!
	if [ -d "$STEAM_RUNTIME" ]; then
		rm -rf "$STEAM_RUNTIME.old"
		if ! mv "$STEAM_RUNTIME" "$STEAM_RUNTIME.old"; then
			return 3
		fi
	fi
	if ! mv "$EXTRACT_TMP"/* "$EXTRACT_TMP"/..; then
		return 4
	fi
	rm -rf "$EXTRACT_TMP"
	if ! cp "$STEAM_RUNTIME.checksum" "$STEAM_RUNTIME/checksum"; then
		return 5
	fi
	return 0
}

#determine platform
UNAME=`uname`
if [ "$UNAME" == "Linux" ]; then

	# identify Linux distribution and pick an optimal bin dir
	PLATFORM=`detect_platform`
	PLATFORM32=`echo $PLATFORM | fgrep 32`
	PLATFORM64=`echo $PLATFORM | fgrep 64`
	if [ -z "$PLATFORM32" ]; then
		PLATFORM32=`echo $PLATFORM | sed 's/64/32/'`
	fi
	if [ -z "$PLATFORM64" ]; then
		PLATFORM64=`echo $PLATFORM | sed 's/32/64/'`
	fi

	# common variables for later

	# We use ~/.steam for bootstrap symlinks so that we can easily
	# tell partners where to go to find the Steam libraries and data.
	# This is constant so that legacy applications can always find us in the future.
	STEAMCONFIG=~/.steam
	PIDFILE="$STEAMCONFIG/steam.pid" # pid of running steam for this user
	STEAMBIN32LINK="$STEAMCONFIG/bin32"
	STEAMBIN64LINK="$STEAMCONFIG/bin64"
	STEAMSDK32LINK="$STEAMCONFIG/sdk32" # 32-bit steam api library
	STEAMSDK64LINK="$STEAMCONFIG/sdk64" # 64-bit steam api library
	STEAMROOTLINK="$STEAMCONFIG/root" # points at the Steam install path for the currently running Steam
	STEAMDATALINK="`detect_steamdatalink`" # points at the Steam content path
	STEAMSTARTING="$STEAMCONFIG/starting"

	# See if this is the initial launch of Steam
	if [ ! -f "$PIDFILE" ] || ! kill -0 $(cat "$PIDFILE") 2>/dev/null; then
		INITIAL_LAUNCH=true
	fi

	if [ "$INITIAL_LAUNCH" ]; then
		# See if we need to update the /usr/bin/steam script
		if [ -z "$STEAMSCRIPT" ]; then
			STEAMSCRIPT="/usr/bin/`detect_package`"
		fi
		if [ -f "$STEAMSCRIPT" ]; then
			if ! check_scriptversion "$STEAMSCRIPT" STEAMSCRIPT_VERSION "$MINIMUM_STEAMSCRIPT_VERSION"; then
				STEAMSCRIPT_OUTOFDATE=1
				warn_outofdate
			fi
		fi

		# Install any additional dependencies
		STEAMDEPS="`dirname $STEAMSCRIPT`/`detect_package`deps"
		if [ -f "$STEAMDEPS" -a -f "$STEAMROOT/steamdeps.txt" ]; then
			"$STEAMDEPS" $STEAMROOT/steamdeps.txt
		fi

		# Create symbolic links for the Steam API
		if [ ! -e "$STEAMCONFIG" ]; then
			mkdir "$STEAMCONFIG"
		fi
		if [ "$STEAMROOT" != "$STEAMROOTLINK" -a "$STEAMROOT" != "$STEAMDATALINK" ]; then
			rm -f "$STEAMBIN32LINK" && ln -s "$STEAMROOT/$PLATFORM32" "$STEAMBIN32LINK"
			rm -f "$STEAMBIN64LINK" && ln -s "$STEAMROOT/$PLATFORM64" "$STEAMBIN64LINK"
			rm -f "$STEAMSDK32LINK" && ln -s "$STEAMROOT/linux32" "$STEAMSDK32LINK"
			rm -f "$STEAMSDK64LINK" && ln -s "$STEAMROOT/linux64" "$STEAMSDK64LINK"
			rm -f "$STEAMROOTLINK" && ln -s "$STEAMROOT" "$STEAMROOTLINK"
			if [ "$STEAMDATALINK" ]; then
				rm -f "$STEAMDATALINK" && ln -s "$STEAMDATA" "$STEAMDATALINK"
			fi
		fi

		# Temporary bandaid until everyone has the new libsteam_api.so
		rm -f ~/.steampath && ln -s "$STEAMCONFIG/bin32/steam" ~/.steampath
		rm -f ~/.steampid && ln -s "$PIDFILE" ~/.steampid
		rm -f ~/.steam/bin && ln -s "$STEAMBIN32LINK" ~/.steam/bin
		# Uncomment this line when you want to remove the bandaid
		#rm -f ~/.steampath ~/.steampid ~/.steam/bin
	fi

	# Show what we detect for distribution and release
	echo "Running Steam on $(distro_description)"

	# prepend our lib path to LD_LIBRARY_PATH
	if [ "$STEAM_RUNTIME" = "1" ]; then
		echo "STEAM_RUNTIME is enabled by the user"
		export STEAM_RUNTIME="$STEAMROOT/$PLATFORM/steam-runtime"
	elif [ "$STEAM_RUNTIME" = "0" ]; then
		echo "STEAM_RUNTIME is disabled by the user"
	elif [ -z "$STEAM_RUNTIME" ]; then
		if runtime_supported; then
			echo "STEAM_RUNTIME is enabled automatically"
			export STEAM_RUNTIME="$STEAMROOT/$PLATFORM/steam-runtime"
		else
			echo "STEAM_RUNTIME is disabled automatically"
		fi
	else
		echo "STEAM_RUNTIME has been set by the user to: $STEAM_RUNTIME"
	fi
	if [ "$STEAM_RUNTIME" ]; then
		# Unpack the runtime if necessary
		if unpack_runtime; then
			case $(uname -m) in
			*64)
				export PATH="$STEAM_RUNTIME/amd64/bin:$STEAM_RUNTIME/amd64/usr/bin:$PATH"
				;;
			*)
				export PATH="$STEAM_RUNTIME/i386/bin:$STEAM_RUNTIME/i386/usr/bin:$PATH"
				;;
			esac

			export LD_LIBRARY_PATH="$STEAM_RUNTIME/i386/lib/i386-linux-gnu:$STEAM_RUNTIME/i386/lib:$STEAM_RUNTIME/i386/usr/lib/i386-linux-gnu:$STEAM_RUNTIME/i386/usr/lib:$STEAM_RUNTIME/amd64/lib/x86_64-linux-gnu:$STEAM_RUNTIME/amd64/lib:$STEAM_RUNTIME/amd64/usr/lib/x86_64-linux-gnu:$STEAM_RUNTIME/amd64/usr/lib:$LD_LIBRARY_PATH"
		else
			echo "Unpack runtime failed, error code $?"
			show_message --error $"Couldn't set up the Steam Runtime. Are you running low on disk space?\nContinuing..."
		fi
	fi
	export LD_LIBRARY_PATH="$STEAMROOT/$PLATFORM:$LD_LIBRARY_PATH"

	# disable SDL1.2 DGA mouse because we can't easily support it in the overlay
	export SDL_VIDEO_X11_DGAMOUSE=0

else # if [ "$UNAME" == "Darwin" ]; then
   PLATFORM=osx32
   # prepend our lib path to LD_LIBRARY_PATH
   export DYLD_LIBRARY_PATH="$STEAMROOT/$PLATFORM:$DYLD_LIBRARY_PATH"
   # make sure our architecture is sane
   ARCH=`arch`
   case "$ARCH" in
      ppc* )
	    osascript -e 'tell application "Dock" 
			display dialog "Steam is only supported on Intel-based Macs." buttons "Exit" default button 1 with title "Unsupported Architecture" with icon stop
			activate
			end tell'
		exit -1
	  ;;
   esac
   # make sure we're running >= 10.5.0
   OSXVER=`sw_vers -productVersion`
   case "$OSXVER" in
      10.0.* | 10.1.* | 10.2.* | 10.3.* | 10.4.* )
	    osascript -e 'tell application "Dock" 
			display dialog "Steam Requires OSX 10.5 or greater" buttons "Exit" default button 1 with title "Unsupported Operating System" with icon stop
			activate
			end tell'
		exit -1
	  ;;
   esac  
fi

ulimit -n 2048

# Touch our startup file so we can detect bootstrap launch failure
if [ "$UNAME" = "Linux" ]; then
	: >"$STEAMSTARTING"
fi

MAGIC_RESTART_EXITCODE=42

# and launch steam
STEAM_DEBUGGER=$DEBUGGER
unset DEBUGGER # Don't use debugger if Steam launches itself recursively
if [ "$STEAM_DEBUGGER" == "gdb" ] || [ "$STEAM_DEBUGGER" == "cgdb" ]; then
	ARGSFILE=$(mktemp $USER.steam.gdb.XXXX)

	# Set the LD_PRELOAD varname in the debugger, and unset the global version. 
	if [ "$LD_PRELOAD" ]; then
		echo set env LD_PRELOAD=$LD_PRELOAD >> "$ARGSFILE"
		echo show env LD_PRELOAD >> "$ARGSFILE"
		unset LD_PRELOAD
	fi

	$STEAM_DEBUGGER -x "$ARGSFILE" "$STEAMROOT/$PLATFORM/$STEAMEXE" "$@"
	rm "$ARGSFILE"
elif [ "$STEAM_DEBUGGER" == "valgrind" ]; then
	DONT_BREAK_ON_ASSERT=1 G_SLICE=always-malloc G_DEBUG=gc-friendly valgrind --error-limit=no --undef-value-errors=no --suppressions=$PLATFORM/steam.supp $STEAM_VALGRIND "$STEAMROOT/$PLATFORM/$STEAMEXE" "$@" 2>&1 | tee steam_valgrind.txt
else
	$STEAM_DEBUGGER "$STEAMROOT/$PLATFORM/$STEAMEXE" "$@"
fi
STATUS=$?

# Restore paths before unpacking the bootstrap if we need to.
export PATH="$SYSTEM_PATH"
export LD_LIBRARY_PATH="$SYSTEM_LD_LIBRARY_PATH"

if [ "$UNAME" = "Linux" ]; then
	if [ "$INITIAL_LAUNCH" -a \
	     $STATUS -ne $MAGIC_RESTART_EXITCODE -a \
	     -f "$STEAMSTARTING" -a \
	     -z "$STEAM_INSTALLED_BOOTSTRAP" -a \
	     -z "$STEAMSCRIPT_OUTOFDATE" ]; then
		# Launching the bootstrap failed, try reinstalling
		if install_bootstrap; then
			# We were able to reinstall the bootstrap, try again
			export STEAM_INSTALLED_BOOTSTRAP=1
			STATUS=$MAGIC_RESTART_EXITCODE
		fi
	fi
fi

if [ $STATUS -eq $MAGIC_RESTART_EXITCODE ]; then
	# are we running running from a bundle on osx?
	if [ $PLATFORM == "osx32" -a -f Info.plist ]; then
		exec open "$STEAMROOT/../.."
	else
		exec "$0" "$@"
	fi
fi
