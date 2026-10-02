# host-path.sh
# Turns a repo-relative path into the form docker wants on the left side of a
# bind mount. Sourced by the scripts that run one-off containers.
#
# Git Bash rewrites arguments that look like absolute POSIX paths, which turns
# a container-side /out into C:/Program Files/Git/out -- so the mount points
# at nothing, or the command names a file that does not exist. cygpath
# produces the host path Windows wants, and MSYS_NO_PATHCONV switches the
# rewriting off. On Linux and macOS neither applies and paths pass through
# unchanged.
#
# The environment is set here, at source time, rather than inside host_path:
# callers use it as "$(host_path some/dir)", which runs in a subshell, and an
# export from a subshell never reaches the script that needs it.

if command -v cygpath >/dev/null 2>&1; then
    MSYS_NO_PATHCONV=1
    MSYS2_ARG_CONV_EXCL='*'
    export MSYS_NO_PATHCONV MSYS2_ARG_CONV_EXCL
fi

host_path() {
    directory="$(pwd)/$1"

    if command -v cygpath >/dev/null 2>&1; then
        directory=$(cygpath --windows "${directory}")
    fi

    printf '%s' "${directory}"
}
