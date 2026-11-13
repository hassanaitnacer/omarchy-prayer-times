### Repository URL

https://github.com/hassanaitnacer/omarchy-prayer-times

### Category

Widgets

### Tags

bar, quickshell

### Suggest a missing tag

_No response_

### Maintainer notes

Prayer Times (io.github.hassanaitnacer.prayer-times) is a bar widget with offline prayer calculations, authoritative Hijri synchronization and a shared reminder service. It supports manual coordinates, IANA timezones, multiple calculation methods, per-prayer adjustments, and English/Arabic/French. New installations require explicit location and method confirmation. Estimated high-latitude times and unavailable polar events are labelled; calculations do not guarantee agreement with local published timetables.

Targets Omarchy 4.5 with the built-in bar. Dependencies: Python 3.9+, system tzdata, Omarchy/Quickshell; mpv is optional for local audio. No pip packages, privileged setup, or bundled third-party recordings. Hijri synchronization fetches the fixed HTTPS Habous homepage hourly after setup, without sending coordinates. The website adapter validates explicit dated announcements and caches confirmed dates; unsupported authorities and unconfirmed month boundaries show unverified. This first source supports Morocco, not all countries. The preview is a rendering of the real panel using the repository's offscreen test harness. Settings are written only to this plugin's bar entry; reminder history and an optional generated chime use the user's XDG state directory. Runtime files and tests are MIT licensed.

### Submission checklist

- [ ] The repository is public and contains installation and removal instructions.
- [ ] I have documented the plugin license and any external dependencies.
- [ ] I confirm that I own or have permission to submit this plugin and its preview assets.
- [ ] The plugin does not overwrite user configuration without explicit consent.
- [ ] I understand that approval is for listing and is not a security review.
