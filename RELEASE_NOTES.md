# Y2JB Installer v2.0.0

A fresh standalone implementation that installs YouTube and the official Y2JB Autoloader image, then exits.

Targets privileged PS5 firmware 13.60 and US YouTube `PPSA01650` (`v01.000.030`). Close YouTube before running. Your profile must already meet the app's account requirements.

Uses the unchanged official `download0.dat` from Y2JB Autoloader `v1.1.0-ba879c8`. The image is verified before and after installation; an existing image is backed up first.

Source, upstream components, the official compressed image, and SDK/library source archives are included in the repository. Build inputs are pinned and hash-verified.

**Validation:** Host build and eight tests passed. Console testing of v2.0.0 is pending.

Credit to Gezine for Y2JB, itsPLK for Y2JB Autoloader, jamesst20 for the upstream installation components, and the SDK/library contributors.
