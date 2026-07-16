#!/bin/bash
set -euo pipefail

INTERVAL="${1:-1}"

watch -n "$INTERVAL" 'date +"%H:%M:%S"; echo; busctl --system get-property org.mpris.MediaPlayer2.ShairportSync /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player Metadata; echo; busctl --system get-property org.mpris.MediaPlayer2.ShairportSync /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player PlaybackStatus; busctl --system get-property org.mpris.MediaPlayer2.ShairportSync /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player Volume'
