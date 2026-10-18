#!/bin/bash
# SPDX-License-Identifier: GPL-2.0+
#
# Record a short video of binman in a terminal, for the docs and website
#
# Usage: record.sh [OUTPUT.webm]
#
# This packages a small image holding U-Boot and TF-A. The U-Boot files are
# stand-ins, made up by this script, but TF-A is fetched and built from source
# by binman, so this needs network access and an aarch64 cross-compiler
# (CROSS_COMPILE, default aarch64-linux-gnu-). Binman runs from this checkout,
# using $PYTHON (default python3), which must have binman's dependencies. A
# scratch home directory is used, so the user's blob cache is not changed.
#
# This needs Xvfb, xterm, tmux, ffmpeg, dtc and lz4. It writes OUTPUT.webm,
# with an MP4 copy and a poster image beside it.

set -e
HERE=$(dirname "$(readlink -f "$0")")
BINMAN_DIR=$(readlink -f "$HERE/../..")
OUT=$(readlink -f "${1:-$PWD/binman-demo.webm}")
PYTHON=${PYTHON:-python3}
DISP=:98
W=1280
H=720
SESS=bdemo

WORK=$(mktemp -d -t binman-demo.XXXXXX)
cleanup() {
	[ -n "$FF" ] && kill -INT $FF 2>/dev/null && wait $FF 2>/dev/null || true
	tmux -L bdemo kill-session -t $SESS 2>/dev/null || true
	[ -n "$XT" ] && kill $XT 2>/dev/null || true
	[ -n "$XV" ] && kill $XV 2>/dev/null || true
}
trap 'cleanup; [ -d "$WORK" ] && rm -rf "$WORK"' EXIT

# Stand-ins for the U-Boot build output, which compress a little, like code
mkdir "$WORK/board"
cd "$WORK/board"
"$PYTHON" - <<'EOF'
import random

random.seed(1)
WORDS = b'binman u-boot image entry offset size section fdtmap blob'.split()

def make(fname, size):
    data = bytearray()
    while len(data) < size:
        data += random.choice(WORDS) + b' '
        if random.random() < 0.3:
            data += random.randbytes(8)
    with open(fname, 'wb') as outf:
        outf.write(data[:size])

make('u-boot-nodtb.bin', 400 * 1024)
make('u-boot-new.bin', 412 * 1024)
EOF
printf '/dts-v1/;\n/ {\n\tmodel = "Demo board";\n};\n' |
	dtc -q -O dtb -o u-boot.dtb -
cat u-boot-nodtb.bin u-boot.dtb > u-boot.bin

cat > image.dts <<'EOF'
/dts-v1/;

/ {
	binman {
		filename = "image.bin";
		size = <0x100000>;
		pad-byte = <0xff>;
		allow-repack;

		u-boot {
		};
		atf-bl31 {
			offset = <0x80000>;
			compress = "lz4";
		};
		fdtmap {
		};
	};
};
EOF

# Run binman from this checkout, under its usual name
mkdir "$WORK/bin"
printf '#!/bin/sh\nPYTHONPATH="%s" exec %s -m binman "$@"\n' \
	"$BINMAN_DIR" "$PYTHON" > "$WORK/bin/binman"
chmod +x "$WORK/bin/binman"
PATH="$WORK/bin:$PATH"

Xvfb $DISP -screen 0 ${W}x${H}x24 -nolisten tcp &
XV=$!
sleep 1

tmux -L bdemo -f /dev/null new-session -d -s $SESS -x 140 -y 40 \
	"env -u XDG_CACHE_HOME -u BINMAN_BLOB_DIR -u BINMAN_BLOB_BUILD_DIR HOME=$WORK PATH=$PATH PS1='\[\e[1;32m\]board\[\e[0m\] \$ ' bash --norc --noprofile"
tmux -L bdemo set -t $SESS status off
tmux -L bdemo send-keys -t $SESS "cd $WORK/board; clear" Enter
sleep 0.5

DISPLAY=$DISP xterm -fa 'DejaVu Sans Mono' -fs 13 -geometry 140x40+0+0 \
	-bg '#1d1f21' -fg '#e0e0e0' -bc -b 12 \
	-xrm 'XTerm*cursorColor: #e0e0e0' -e tmux -L bdemo attach -t $SESS &
XT=$!
sleep 1.5

RAW=$WORK/raw.mkv
ffmpeg -loglevel error -y -f x11grab -draw_mouse 0 -framerate 25 \
	-video_size ${W}x${H} -i $DISP -c:v libx264rgb -crf 0 -preset ultrafast \
	$RAW &
FF=$!
START=$(date +%s.%N)
sleep 1

# Type a command a character at a time, run it, wait for it to finish and
# then leave its output on the screen for a while
run() {
	local cmd=$1 wait=${2:-2}
	local i
	for ((i = 0; i < ${#cmd}; i++)); do
		tmux -L bdemo send-keys -t $SESS -l "${cmd:i:1}"
		sleep 0.03
	done
	sleep 0.4
	tmux -L bdemo send-keys -t $SESS Enter
	sleep 0.3
	while [ "$(tmux -L bdemo display -p -t $SESS \
		'#{pane_current_command}')" != bash ]; do
		sleep 0.2
	done
	sleep "$wait"
}

# Show a comment, as the viewer's guide to what comes next
say() {
	run "# $1" 0.8
}

BUILD="binman build -u -d image.dts -I . -O out -a atf-bl31-path=bl31.bin"
BLOB=arm,trusted-firmware-a

say "An image holding U-Boot and TF-A, described in a devicetree"
run "cat image.dts" 4
run "clear" 0.3
say "Build it from the U-Boot output here, allowing TF-A to be missing"
run "$BUILD -M" 4
say "Binman can build TF-A from source and keep it in its cache"
run "binman blob --fetch $BLOB --version 2.12 --arch aarch64 --plat sun50i_a64" 3
run "cp ~/.cache/binman/blobs/$BLOB/2.12/aarch64/sun50i_a64/bl31.bin ." 0.5
say "Build the image again, now that it is complete"
run "$BUILD" 1.5
run "clear" 0.3
say "See what is in the image and where"
run "binman ls -i out/image.bin" 1
POSTER=$(awk "BEGIN { print $(date +%s.%N) - $START }")
sleep 3
say "Extract an entry, which binman decompresses"
run "binman extract -i out/image.bin atf-bl31 -f bl31.out && cmp bl31.out bl31.bin && echo same" 2.5
say "Replace U-Boot with a larger one, so binman repacks the image"
run "binman replace -i out/image.bin u-boot -f u-boot-new.bin" 0.5
run "binman ls -i out/image.bin" 4

cleanup
FF=
trap - EXIT
ffmpeg -loglevel error -y -i $RAW -c:v libvpx-vp9 -b:v 0 -crf 30 -row-mt 1 \
	-pix_fmt yuv420p "$OUT"
ffmpeg -loglevel error -y -i $RAW -c:v libx264 -crf 26 -preset slow \
	-pix_fmt yuv420p -movflags +faststart "${OUT%.webm}.mp4"
ffmpeg -loglevel error -y -ss "$POSTER" -i $RAW -frames:v 1 "${OUT%.webm}.png"
rm -rf "$WORK"
echo "Wrote $OUT, ${OUT%.webm}.mp4 and ${OUT%.webm}.png"
