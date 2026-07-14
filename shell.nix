# fork: NixOS dev shell for openpilot.
#
# openpilot vendors its native deps (acados, capnp, ffmpeg, zeromq, libyuv, ...)
# as prebuilt manylinux wheels installed by `uv sync`. Those binaries expect a
# standard FHS layout, which NixOS doesn't provide -- so we run inside a
# buildFHSEnv sandbox where they (and the scons-built C++) link cleanly.
#
# Usage:
#   nix-shell                       # drops you into the FHS shell
#   uv sync --frozen --all-extras   # first time: build the .venv from wheels
#   source .venv/bin/activate
#   scons -j$(nproc)                # build openpilot
#   # then: pytest, process_replay, etc.
#
# `./tools/op.sh setup` is NOT used here: its Linux path only knows apt/dnf/etc
# and has no NixOS branch. This shell replaces the system-deps step; you still
# run the git submodule / lfs / uv steps yourself (see below).

{ pkgs ? import <nixpkgs> { } }:

(pkgs.buildFHSEnv {
  name = "openpilot-dev";

  targetPkgs = p: (with p; [
    # --- toolchain (scons compiles openpilot's own C++) ---
    gcc gnumake binutils pkg-config cmake

    # --- python + uv (uv manages the venv and all the vendored wheels) ---
    python312
    uv

    # --- vcs / fetch (submodules, lfs, uv downloads) ---
    git git-lfs curl cacert openssl

    # --- runtime libs the prebuilt wheels & UI binaries dlopen/link ---
    stdenv.cc.cc.lib   # libstdc++ / libgcc_s
    zlib bzip2 zstd xz
    glib
    ffmpeg
    libusb1            # panda / usb
    ncurses

    # tinygrad's LLVM CPU backend dlopens libLLVM.so from /lib at model-compile
    # time (it ignores LLVM_PATH/LD_LIBRARY_PATH and scans /lib,/lib64). Provide
    # libLLVM.so + its NEEDED deps (libffi, libxml2).
    llvmPackages.libllvm.lib
    libffi
    libxml2

    # graphics for the raylib UI + MetaDrive sim
    libGL libGLU
    mesa               # EGL / GLESv2 / gbm
    libdrm
    libxkbcommon
    wayland
    xorg.libX11 xorg.libXext xorg.libXrandr xorg.libXinerama
    xorg.libXcursor xorg.libXi xorg.libXrender xorg.libXfixes
    xorg.xorgserver xorg.xauth   # Xvfb, for the UI render/report (setup_xvfb.sh)
    fontconfig freetype

    # handy
    which gnutar gzip procps
  ]);

  # Entering the shell: point uv at the nix python (don't let it fetch a
  # standalone interpreter), wire up certs, and put the repo on PYTHONPATH.
  profile = ''
    export UV_PYTHON_DOWNLOADS=never
    export UV_PYTHON=${pkgs.python312}/bin/python3.12
    export PYTHONPATH="$PWD"
    export SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt
    export GIT_SSL_CAINFO="$SSL_CERT_FILE"
    export CURL_CA_BUNDLE="$SSL_CERT_FILE"
    # restore the repo-root submodule symlinks (opendbc -> opendbc_repo/opendbc,
    # etc.) if a checkout dropped them -- import opendbc/msgq resolve off these.
    for l in opendbc msgq rednose teleoprtc tinygrad; do
      [ -e "$l" ] || git checkout -- "$l" 2>/dev/null || true
    done
    # activate the venv automatically if it already exists
    if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
    echo "openpilot FHS dev shell. First time: 'uv sync --frozen --all-extras' then 'scons -j\$(nproc)'."
  '';

  runScript = "bash";
}).env
