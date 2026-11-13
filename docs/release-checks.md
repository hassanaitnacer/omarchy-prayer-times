# First public release checks

Target: Omarchy 4.5.0-3, built-in bar. Plugin version: 2.0.0.

## Completed locally

- Installed Omarchy manifest validator passes. The manifest uses marketplace-compatible `defaultSection: center`.
- 46 Python tests pass: original calculation/calendar/delivery cases, independent Raleigh/Cairo and Edinburgh references (Edinburgh tolerance: one minute), seasonal ordering in Sydney/Cape Town/Tokyo/Karachi/São Paulo/Singapore, invalid-location fail-quiet behavior, setup confirmation gating, official Habous date parsing, cache/offline behavior, explicit month boundaries, and authoritative date rollover through the daemon loop.
- JavaScript display-helper test file passes (three test cases).
- Seven offscreen QML scenarios pass: English panel and calculation settings, French city chooser and Tokyo setup confirmation, Arabic fasting layout, initial setup, and the cached authoritative date.
- All three translation catalogs have matching keys.
- QML lint exits successfully when the installed shell is exposed under a temporary `qs` import path. It still reports dynamic host-property and unqualified-access warnings; this is not a warning-free lint result. Runtime rendering is checked separately.
- No symlinks or generated Python caches are included in the Git index. No user home paths or credentials were found in the published runtime files.

## Remaining integration checks

The official Habous page was inspected and confirms November 13, 2026 = Jumada II 3, 1448. Parser tests use that published date pair. Direct HTTPS from the plugin process is not testable under this environment’s network restrictions; verify the live adapter before publication.

A real desktop shell is unavailable from the preparation environment. Before marketplace submission, verify fresh installation, bar click/Escape and IPC summon/hide, disable/re-enable, restart, removal, actual notifications, audio stop, and suspend/resume on the desktop. Offscreen rendering does not cover these integrations.

The owner will publish using their SSH key. Run `git push -u origin main` from this repository with GitHub access, then verify the remote manifest and README. No issue has been submitted. Review the title `[Plugin]: Prayer Times` and `marketplace-submission.md`; confirm all five statements and check them only when true before submitting.

The local installation was migrated to a separate ordinary Git checkout under the permanent ID, with the previous source and settings backed up. Effective Casablanca location/method defaults were preserved and setup was marked complete only for that existing installation. No manual Hijri offset was applied. Unrelated settings were compared and verified unchanged. Fresh installations retain `setupComplete: false`. Desktop rendering of the installed checkout and live HTTPS remain unverified from this preparation environment.
