# AirPlay metadata setup

A Clockwork Plex can show metadata from Shairport Sync on the AirPlay screen. This is a separate layer from the AirPlay start/stop handoff hooks:

```text
AirPlay session hooks
  → decide whether AirPlay is active
  → stop/start Plexamp
  → switch the dashboard screen

AirPlay metadata listener
  → reads Shairport Sync metadata pipe
  → stores title/artist/album/volume/artwork for /api/status
  → lets the AirPlay screen update live
```

## 1. Check Shairport Sync was built with metadata support

```bash
shairport-sync -V
```

Look for metadata support in the version string. The pipe listener also needs Shairport Sync's metadata pipe feature. Most Raspberry Pi packages that include metadata support should be fine, but this is the bit to check first if no metadata appears.

## 2. Install the A Clockwork Plex metadata listener

```bash
cd ~/A-Clockwork-Plex
git pull
chmod +x scripts/*.sh
./scripts/install-airplay-metadata-listener.sh
```

The helper creates:

```text
/tmp/shairport-sync-metadata
/etc/systemd/system/a-clockwork-plex-airplay-metadata.service
```

It then starts and enables the listener service.

## 3. Add metadata settings to Shairport Sync

Edit the config:

```bash
sudo nano /etc/shairport-sync.conf
```

Add or update this top-level block:

```conf
metadata =
{
    enabled = "yes";
    include_cover_art = "yes";
    pipe_name = "/tmp/shairport-sync-metadata";
    pipe_timeout = 5000;
};
```

Then validate and restart:

```bash
shairport-sync -t
sudo systemctl restart shairport-sync
```

## 4. Watch the logs

Metadata listener logs:

```bash
journalctl -u a-clockwork-plex-airplay-metadata.service -f
```

AirPlay handoff logs:

```bash
journalctl -t shairport-plexamp -f
```

Dashboard status:

```bash
curl -s http://localhost:8088/api/status | python -m json.tool
```

When metadata arrives, look under:

```text
state.airplay.metadata
```

## Metadata pipe format

Shairport Sync sends metadata to the pipe in a line-oriented XML-style format, not as raw binary frames. Each item starts with a header line like this:

```text
73736e63`70626567`0
636f7265`6d696e6d`11
```

The first value is the 4-byte metadata type as hex, the second is the 4-byte code as hex, and the third is the decoded payload length. Payloads, including artwork, are base64 encoded after a blank separator line.

The A Clockwork Plex listener decodes that stream directly. If you see lots of old log lines like this, the listener is too old and should be updated:

```text
Skipping suspicious metadata frame ... length=...
```

## What should appear

Depending on the sending app, Shairport Sync may provide:

```text
title
artist
album
genre
source_name
source_model
volume
client_ip
artwork_url
```

Not every iPhone app sends all fields. Apple Music usually behaves well; podcast and radio apps can be more coy, because apparently even metadata has commitment issues.

## Troubleshooting

### AirPlay switches screens but no title/artist appears

Check the metadata service:

```bash
systemctl status a-clockwork-plex-airplay-metadata.service --no-pager
journalctl -u a-clockwork-plex-airplay-metadata.service -n 80 --no-pager
```

Check the FIFO exists:

```bash
ls -l /tmp/shairport-sync-metadata
```

It should be a pipe, shown with a leading `p`, for example:

```text
prw-rw-rw- 1 root root ... /tmp/shairport-sync-metadata
```

### Shairport fails to start after config edit

Run:

```bash
shairport-sync -t
```

The config block must be top-level, not nested inside `general`, `sessioncontrol` or `alsa`.

### Artwork does not appear

Some apps send text metadata but no artwork. The dashboard still shows title/artist/album when available. Generated artwork is stored at:

```text
app/static/generated/airplay-cover.jpg
app/static/generated/airplay-cover.png
```
