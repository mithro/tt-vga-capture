#!/bin/bash
OUT=$1
cd $HOME/github/TinyTapeout/vgacap/.worktrees/bench-43
export GST_PLUGIN_PATH=$PWD/build
uv run ttcap capture ws://127.0.0.1:18034/serial --clock-hz 500000 --seconds 0 --out - |
    gst-launch-1.0 -e fdsrc fd=0 ! application/x-vgacap ! vgadecode ! \
    videoconvert ! pngenc ! multifilesink location=$OUT/frame-%04d.png
echo "PIPESTATUS ${PIPESTATUS[@]}"
