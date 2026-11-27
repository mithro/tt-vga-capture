# Hardware-in-the-loop check: fpga-1 (ws://127.0.0.1:18034/serial)

Date: 2026-11-27 12:15:20+1030

| | |
|---|---|
| board | `fpga-1` |
| link | `ws://127.0.0.1:18034/serial` |
| design / project | `tt_um_vgacal_bars` |
| project clock | 400000 Hz (a 640x480 frame is 1.050 s) |
| capture length | 10.0 s, video re-timed to 5 fps |
| host | `big-storage`, 3.14.3 |
| vgacap | `20f99bf` |
| `ttcap` | `uv run --no-sync ttcap` |
| verdict | **PASS** |

## Checks

| check | result | measured |
|---|---|---|
| `probe` | PASS | fpga-1 (ws://127.0.0.1:18034/serial) answered in 0.3s: sys.version: 3.4.0; MicroPython 970468103d on 2026-09-08 / GPIOMap.all(): {'mng00': 3, 'mng01': 4, 'mng02': 5, 'mng03': 6, 'adc3': 43, 'mng04': 7, 'mng05': 8, 'mng06': 9, 'mng07': 10, 'uo_out6': 39, 'uo_out7': 40, 'uo_out4': 37, 'uo_out5': 38, 'rp_projclk': 16, 'uo_out0': 33, 'uo_out1': 34, 'uo_out2 |
| `capture` | PASS | fpga-1 (ws://127.0.0.1:18034/serial): bytes=3918710 samples=3915776 chunks=240 seconds=10.032 overruns=0 dropped=0 rxstall=0 samples_per_s=390328 mem_free=419472, 3918821 byte(s) on disk |
| `reconstruct` | PASS | 8 frame(s) from 3918821 byte(s), wanted >=7 for 10.0s at 400000 Hz; frames=8 glitches_total=0 |
| `reference` | PASS | tt_um_vgacal_bars vs f-0004.ppm: PASS: 307200 pixels identical to the reference render |
| `frame` | PASS | 2 of 2 picture(s) pixel-exact at 25000000 Hz (640x480@60); board: frames=2 stalls=0 rxstall=0 sysclk_hz=100000000 |
| `demo-frames` | PASS | exit 0, 37 png(s) in 11.1s, wanted >=25 at 5 fps |
| `video` | PASS | capture.mkv: 7.40s at 5/1, 18234 byte(s); 37 frames at 5 fps is 7.40s |
| `serve` | PASS | 31 MJPEG part(s) from http://127.0.0.1:8099/stream.mjpg (multipart/x-mixed-replace; boundary=vgacapframe) |
| `stop` | PASS | SIGTERM -> exit 0 in 0.26s (budget 15s), 0 orphan(s), capture.mkv duration 2.20s |
| `board-usable` | PASS | fpga-1 (ws://127.0.0.1:18034/serial) answered in 0.4s: sys.version: 3.4.0; MicroPython 970468103d on 2026-09-08 / GPIOMap.all(): {'mng00': 3, 'mng01': 4, 'mng02': 5, 'mng03': 6, 'adc3': 43, 'mng04': 7, 'mng05': 8, 'mng06': 9, 'mng07': 10, 'uo_out6': 39, 'uo_out7': 40, 'uo_out4': 37, 'uo_out5': 38, 'rp_projclk': 16, 'uo_out0': 33, 'uo_out1': 34, 'uo_out2 |

## Evidence

### `probe` -- PASS

fpga-1 (ws://127.0.0.1:18034/serial) answered in 0.3s: sys.version: 3.4.0; MicroPython 970468103d on 2026-09-08 / GPIOMap.all(): {'mng00': 3, 'mng01': 4, 'mng02': 5, 'mng03': 6, 'adc3': 43, 'mng04': 7, 'mng05': 8, 'mng06': 9, 'mng07': 10, 'uo_out6': 39, 'uo_out7': 40, 'uo_out4': 37, 'uo_out5': 38, 'rp_projclk': 16, 'uo_out0': 33, 'uo_out1': 34, 'uo_out2

```
uv run --no-sync ttcap probe ws://127.0.0.1:18034/serial
```

### `capture` -- PASS

fpga-1 (ws://127.0.0.1:18034/serial): bytes=3918710 samples=3915776 chunks=240 seconds=10.032 overruns=0 dropped=0 rxstall=0 samples_per_s=390328 mem_free=419472, 3918821 byte(s) on disk

```
uv run --no-sync ttcap capture ws://127.0.0.1:18034/serial --clock-hz 400000 --seconds 10.0 --profile auto --out vgacap/tmp/hil/hil.vgacap --design tt_um_vgacal_bars
profile=rp2350-dbv3 project=tt_um_vgacal_bars enable=already enabled
bytes=3918710 samples=3915776 chunks=240 seconds=10.032 overruns=0 dropped=0 rxstall=0 samples_per_s=390328 mem_free=419472
  board: overruns=0 rxstall=0 sysclk_hz=132000000
wrote vgacap/tmp/hil/hil.vgacap
```

### `reconstruct` -- PASS

8 frame(s) from 3918821 byte(s), wanted >=7 for 10.0s at 400000 Hz; frames=8 glitches_total=0

```
vgacap/build/vgacap-frames vgacap/tmp/hil/hil.vgacap vgacap/tmp/hil/frames/f
frame 5: 640x480 mode=640x480@60 cpl=800 lpf=525 hsync=neg vsync=neg partial=0 glitches=0
frame 6: 640x480 mode=640x480@60 cpl=800 lpf=525 hsync=neg vsync=neg partial=0 glitches=0
frame 7: 640x480 mode=640x480@60 cpl=800 lpf=525 hsync=neg vsync=neg partial=0 glitches=0
frames=8 glitches_total=0
```

### `reference` -- PASS

tt_um_vgacal_bars vs f-0004.ppm: PASS: 307200 pixels identical to the reference render

```
uv run --no-project --with numpy --with pillow python tools/compare_capture.py tt_um_vgacal_bars vgacap/tmp/hil/frames/f-0004.ppm --ui-in 0
tt_um_vgacal_bars: captured 640x480, reference 640x480 (fixed picture)
PASS: 307200 pixels identical to the reference render
```

### `frame` -- PASS

2 of 2 picture(s) pixel-exact at 25000000 Hz (640x480@60); board: frames=2 stalls=0 rxstall=0 sysclk_hz=100000000

```
uv run --no-sync ttcap capture ws://127.0.0.1:18034/serial --clock-hz 25000000 --mode frame --vga-mode 640x480@60 --frames 2 --seconds 60 --profile auto --out vgacap/tmp/hil/frame.vgacap --design tt_um_vgacal_bars
frame window=478 buffers=64 hsync_active=0 vsync_active=0
frames=2 stalls=0 rxstall=0 sysclk_hz=100000000
f-0000.ppm: PASS: 307200 pixels identical to the reference render
f-0001.ppm: PASS: 307200 pixels identical to the reference render
```

### `demo-frames` -- PASS

exit 0, 37 png(s) in 11.1s, wanted >=25 at 5 fps

```
uv run --no-sync ttcap demo --link ws://127.0.0.1:18034/serial --clock-hz 400000 --seconds 10.0 --profile auto --fps 5 --outdir vgacap/tmp/hil/demo --force --design tt_um_vgacal_bars --serve 8099
writing vgacap/tmp/hil/demo/capture.mkv
writing an MJPEG stream
serving http://127.0.0.1:8099/ -- open it in a browser
gst-launch-1.0 -e -m vgacapttsrc name=src link=ws://127.0.0.1:18034/serial clock-hz=400000 seconds=10 profile=auto 'ttcap-command=uv run --no-sync ttcap' design=tt_um_vgacal_bars ! vgadecode name=dec repeat-last-frame=true output-fps=5/1 ! tee name=t \
    t. ! queue ! pngenc ! multifilesink post-messages=true location=vgacap/tmp/hil/demo/frame-%04d.png \
    t. ! queue ! videoconvert ! x264enc tune=zerolatency speed-preset=veryfast key-int-max=30 ! matroskamux ! filesink location=vgacap/tmp/hil/demo/capture.mkv \
    t. ! queue leaky=downstream max-size-buffers=4 ! videoconvert ! jpegenc ! multipartmux boundary=vgacapframe ! fdsink sync=false fd=5
  mode 640x480@60: 800 clocks/line, 525 lines/frame, hsync negative, vsync negative, glitches 0
  1 frame(s), 3s elapsed
  7 frame(s), 5s elapsed
  12 frame(s), 6s elapsed
  17 frame(s), 7s elapsed
  23 frame(s), 8s elapsed
  28 frame(s), 9s elapsed
  33 frame(s), 10s elapsed
capture finished after 10.8s (gst-launch exit 0)
  mode 640x480@60: 800 clocks/line, 525 lines/frame, hsync negative, vsync negative, glitches 0
  37 png(s) in vgacap/tmp/hil/demo
  vgacap/tmp/hil/demo/capture.mkv, 17.8 KiB
  31 frame(s) published on port 8099
```

### `video` -- PASS

capture.mkv: 7.40s at 5/1, 18234 byte(s); 37 frames at 5 fps is 7.40s

```
uv run --no-sync ttcap demo --link ws://127.0.0.1:18034/serial --clock-hz 400000 --seconds 10.0 --profile auto --fps 5 --outdir vgacap/tmp/hil/demo --force --design tt_um_vgacal_bars --serve 8099
writing vgacap/tmp/hil/demo/capture.mkv
writing an MJPEG stream
serving http://127.0.0.1:8099/ -- open it in a browser
gst-launch-1.0 -e -m vgacapttsrc name=src link=ws://127.0.0.1:18034/serial clock-hz=400000 seconds=10 profile=auto 'ttcap-command=uv run --no-sync ttcap' design=tt_um_vgacal_bars ! vgadecode name=dec repeat-last-frame=true output-fps=5/1 ! tee name=t \
    t. ! queue ! pngenc ! multifilesink post-messages=true location=vgacap/tmp/hil/demo/frame-%04d.png \
    t. ! queue ! videoconvert ! x264enc tune=zerolatency speed-preset=veryfast key-int-max=30 ! matroskamux ! filesink location=vgacap/tmp/hil/demo/capture.mkv \
    t. ! queue leaky=downstream max-size-buffers=4 ! videoconvert ! jpegenc ! multipartmux boundary=vgacapframe ! fdsink sync=false fd=5
  mode 640x480@60: 800 clocks/line, 525 lines/frame, hsync negative, vsync negative, glitches 0
  1 frame(s), 3s elapsed
  7 frame(s), 5s elapsed
  12 frame(s), 6s elapsed
  17 frame(s), 7s elapsed
  23 frame(s), 8s elapsed
  28 frame(s), 9s elapsed
  33 frame(s), 10s elapsed
capture finished after 10.8s (gst-launch exit 0)
  mode 640x480@60: 800 clocks/line, 525 lines/frame, hsync negative, vsync negative, glitches 0
  37 png(s) in vgacap/tmp/hil/demo
  vgacap/tmp/hil/demo/capture.mkv, 17.8 KiB
  31 frame(s) published on port 8099
```

### `serve` -- PASS

31 MJPEG part(s) from http://127.0.0.1:8099/stream.mjpg (multipart/x-mixed-replace; boundary=vgacapframe)

```
uv run --no-sync ttcap demo --link ws://127.0.0.1:18034/serial --clock-hz 400000 --seconds 10.0 --profile auto --fps 5 --outdir vgacap/tmp/hil/demo --force --design tt_um_vgacal_bars --serve 8099
writing vgacap/tmp/hil/demo/capture.mkv
writing an MJPEG stream
serving http://127.0.0.1:8099/ -- open it in a browser
gst-launch-1.0 -e -m vgacapttsrc name=src link=ws://127.0.0.1:18034/serial clock-hz=400000 seconds=10 profile=auto 'ttcap-command=uv run --no-sync ttcap' design=tt_um_vgacal_bars ! vgadecode name=dec repeat-last-frame=true output-fps=5/1 ! tee name=t \
    t. ! queue ! pngenc ! multifilesink post-messages=true location=vgacap/tmp/hil/demo/frame-%04d.png \
    t. ! queue ! videoconvert ! x264enc tune=zerolatency speed-preset=veryfast key-int-max=30 ! matroskamux ! filesink location=vgacap/tmp/hil/demo/capture.mkv \
    t. ! queue leaky=downstream max-size-buffers=4 ! videoconvert ! jpegenc ! multipartmux boundary=vgacapframe ! fdsink sync=false fd=5
  mode 640x480@60: 800 clocks/line, 525 lines/frame, hsync negative, vsync negative, glitches 0
  1 frame(s), 3s elapsed
  7 frame(s), 5s elapsed
  12 frame(s), 6s elapsed
  17 frame(s), 7s elapsed
  23 frame(s), 8s elapsed
  28 frame(s), 9s elapsed
  33 frame(s), 10s elapsed
capture finished after 10.8s (gst-launch exit 0)
  mode 640x480@60: 800 clocks/line, 525 lines/frame, hsync negative, vsync negative, glitches 0
  37 png(s) in vgacap/tmp/hil/demo
  vgacap/tmp/hil/demo/capture.mkv, 17.8 KiB
  31 frame(s) published on port 8099
```

### `stop` -- PASS

SIGTERM -> exit 0 in 0.26s (budget 15s), 0 orphan(s), capture.mkv duration 2.20s

```
uv run --no-sync ttcap demo --link ws://127.0.0.1:18034/serial --clock-hz 400000 --seconds 0 --profile auto --fps 5 --outdir vgacap/tmp/hil/stop --force --design tt_um_vgacal_bars
orphans: none
board link: ws://127.0.0.1:18034/serial (from --link)
writing vgacap/tmp/hil/stop/frame-%04d.png
writing vgacap/tmp/hil/stop/capture.mkv
gst-launch-1.0 -e -m vgacapttsrc name=src link=ws://127.0.0.1:18034/serial clock-hz=400000 seconds=0 profile=auto 'ttcap-command=uv run --no-sync ttcap' design=tt_um_vgacal_bars ! vgadecode name=dec repeat-last-frame=true output-fps=5/1 ! tee name=t \
    t. ! queue ! pngenc ! multifilesink post-messages=true location=vgacap/tmp/hil/stop/frame-%04d.png \
    t. ! queue ! videoconvert ! x264enc tune=zerolatency speed-preset=veryfast key-int-max=30 ! matroskamux ! filesink location=vgacap/tmp/hil/stop/capture.mkv
  mode 640x480@60: 800 clocks/line, 525 lines/frame, hsync negative, vsync negative, glitches 0
  1 frame(s), 3s elapsed
  7 frame(s), 4s elapsed
SIGTERM: asking the pipeline to end the stream. The board needs one DMA buffer to wind down, so give it a moment.
capture finished after 4.9s (gst-launch exit 0)
  mode 640x480@60: 800 clocks/line, 525 lines/frame, hsync negative, vsync negative, glitches 0
  11 png(s) in vgacap/tmp/hil/stop
  vgacap/tmp/hil/stop/capture.mkv, 8.5 KiB
```

### `board-usable` -- PASS

fpga-1 (ws://127.0.0.1:18034/serial) answered in 0.4s: sys.version: 3.4.0; MicroPython 970468103d on 2026-09-08 / GPIOMap.all(): {'mng00': 3, 'mng01': 4, 'mng02': 5, 'mng03': 6, 'adc3': 43, 'mng04': 7, 'mng05': 8, 'mng06': 9, 'mng07': 10, 'uo_out6': 39, 'uo_out7': 40, 'uo_out4': 37, 'uo_out5': 38, 'rp_projclk': 16, 'uo_out0': 33, 'uo_out1': 34, 'uo_out2

```
uv run --no-sync ttcap probe ws://127.0.0.1:18034/serial
```

