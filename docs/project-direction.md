# Keivotos project direction

Keivotos is the shared local-first suite; Waifu-Hoard is its first module.
V1.0.0 establishes the identity, external writable-data layout, source launch,
portable-build path, local verification, and FOSS distribution foundation
needed before more hoarders are combined.

## Next investigation

Waifu-Hoard-Hoarder is the next codebase to evaluate. It already experiments
with manga acquisition, CBZ storage, queueing, local-library scans, and a reader.
The first task is an audit—not a bulk move—covering:

- which reader and library pieces are genuinely reusable;
- per-module indexes versus shared irreplaceable user state;
- one-process module navigation versus separately incubated services;
- content identity across image, manga, video, audio, and text archives; and
- external-tool, network, deletion, and backup boundaries.

Only the smallest complete shared path should be promoted after that contract is
written and regression-protected.

## Longer-term module families

- Manga/comics and comments
- Anime/video and series/episode grouping
- Music and karaoke with synchronized lyrics
- Twitter/Pixiv, Reddit, Telegram, Discord, and other text/thread archives
- 2D, 3D, Live2D, game-asset, and creator-store archives
- YouTube, Kemono, GitHub, and historical web-page archives
- Local rediscovery, memories, folder browsing, and user-tagged meme libraries

These are directions, not commitments in V1.0.0. Each needs a source policy,
storage/backup model, disk-budget behavior, viewer, and data-safety review.

## Deliberately deferred infrastructure

Automatic updates, deployment feeds, code signing, installers, Docker, plugin
APIs, and private/public dual-repository development are intentionally deferred.
They add permanent maintenance and trust obligations; the current manual,
reproducible local artifact build is the correct V1.0.0 boundary. GitHub Actions
automation is deferred to a future release.
