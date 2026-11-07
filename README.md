# Y2JB Installer

A standalone ELF that installs YouTube and the official Y2JB Autoloader image on a privileged PS5 running **firmware 13.60**.

It handles the YouTube installation, writes `download0.dat`, verifies the installed image, and displays a completion notification.

## Download and use

Download `Y2JB-installer.elf` from [Releases](https://github.com/dakotadawolfe/Y2JB-installer/releases/latest).

1. Start a privileged session on firmware 13.60.
2. Close YouTube completely and ensure at least 2 GiB of internal storage is free.
3. Run the installer through your payload loader.
4. Wait for the success notification, then launch YouTube.

The installer targets US YouTube `PPSA01650`, package `v01.000.030`. A matching package is reused; a different package is left alone and installation stops. Your profile must already meet YouTube's account requirements.

It writes the unmodified official `download0.dat`. Existing images are backed up under `/data/y2jb-installer/`. The new image is verified before activation and read back afterward. An interrupted installation can leave YouTube installed; rerunning can finish the image step. The app keeps its normal YouTube name and artwork.

Launching YouTube afterward runs upstream Y2JB Autoloader, which follows its own autoload configuration.

## Build

The repository includes installer source, upstream installation components, Y2JB source, the compressed official image, and pinned SDK/library source archives. `dependencies.json` records origins and hashes. Only the pinned YouTube package parts are downloaded during builds.

Use Linux or WSL with Python 3.11+, Clang/LLVM 18 and LLD, a C/C++ toolchain, make, unzip, tar, autotools, libtool, pkg-config, wget, and Sleuth Kit (`fls`, `icat`, `istat`).

```sh
git clone https://github.com/dakotadawolfe/Y2JB-installer.git
cd Y2JB-installer
python3 -m unittest discover -s tests -v
bash build.sh
```

Outputs are in `dist/`: `Y2JB-installer.elf`, `SHA256SUMS.txt`, and `build-manifest.json`. The SDK and HTTP library are compiled locally. Build intermediates and downloaded packages are stored in `.build/`.

Verification checks dependency hashes, official image identity, sparse reconstruction, UFS2 files and permissions, and embedded assets. Tests cover malformed images, sparse file I/O, and failure handling.

**Validation:** Host build and eight tests passed. Console testing of v2.0.0 is pending.

## Credits

- [Gezine](https://github.com/Gezine/Y2JB): original Y2JB.
- [itsPLK](https://github.com/itsPLK/ps5-y2jb-autoloader): Y2JB Autoloader and the official image.
- [jamesst20](https://github.com/jamesst20/ps5-y2jb-installer): upstream YouTube installation components and package metadata.
- [PS5 Payload SDK contributors](https://github.com/ps5-payload-dev/sdk), GNU libmicrohttpd, cJSON, and upstream contributors.

Installer code is GPL-3.0-or-later; see `LICENSE`. Vendored components retain their own licenses and notices. YouTube content belongs to its respective owners.
