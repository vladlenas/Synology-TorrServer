# TorrServer package for Synology NAS
Synology NAS package for DSM 6.0 and DSM 7.0 based on TorrServer binaries https://github.com/YouROK/TorrServer/releases

You can thank the TorrServer developer here https://github.com/YouROK/TorrServer#donate

# Sopported Architecture
* arm5 - armv5 88f6281 88f628x - no longer supported
* arm7 - armv7 alpine alpine4k armada370 armada375 armada38x armadaxp comcerto2k monaco
* arm64 - aarch64 armv8 rtd1296 armada37xx
* amd64 - apollolake avoton braswell broadwell broadwellnk bromolow cedarview denverton dockerx64 geminilake grantley purley kvmx64 v1000 x86 x86_64
* 386 - evansport apollolake avoton braswell broadwell broadwellnk bromolow cedarview denverton dockerx64 geminilake grantley purley kvmx64 v1000 x86 x86_64

# Automatic update
Add  https://packages.voxel-firmware.com/  to your Synology NAS Package Center sources!

# Making packages from precompiled TorrServer binaries
```
git clone https://github.com/vladlenas/Synology-TorrServer.git
cd Synology-TorrServer/
```
```
make
```
TorrServer version change
```
nano Makefile
TORRSERVER_VERSION="MatriX.84"
PKG_VERSION="1.2.84"
```
# Building binaries from TorrServer source
preparing the environment for compilation
https://github.com/YouROK/TorrServer#build
```
make bin
```
# Clear working directory
```
make clean
```
# Log file
```
/var/packages/TorrServer/target/config/TorrServer.log
```
# Permission DSM 7.0 for write cache to hard drive.
* `Control Panel > Shared Folder > Select Shared Folder > Edit > Permissions > System internal user > TorrServer user add read/write`

# Credits and References
* YouROK https://github.com/YouROK
* Huge thanks for https://github.com/tailscale/tailscale-synology his scripts made it easier to build packages.
* Synology DSM 7.0 Developer Guide https://help.synology.com/developer-guide/
* Architecture per Synology model https://github.com/SynoCommunity/spksrc/wiki/Architecture-per-Synology-model
