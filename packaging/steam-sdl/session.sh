# Sourced after the distribution's session configuration. Preserve its flags
# and optional OpenGamepadUI wrapper; change only the Steam executable.
case "$CLIENTCMD" in
    steam\ *) CLIENTCMD="/usr/bin/steam-flydigi ${CLIENTCMD#steam }" ;;
    *\ --\ steam\ *) CLIENTCMD="${CLIENTCMD/ -- steam / -- /usr/bin/steam-flydigi }" ;;
esac
