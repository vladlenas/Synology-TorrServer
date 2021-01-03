# TorrServer package for Synology NAS
Synology NAS package based on precompiled TorrServer binaries.
https://github.com/YouROK/TorrServer/releases
supported DSM 6.0 and above, not supported DSM 7.0.

# Making packages
```
git clone https://github.com/vladlenas/Synology-TorrServer.git
cd Synology-TorrServer/
make
```
TorrServer version change
```
nano Makefile ### TORRSERVER_VERSION="1.1.77"
```
clear working directory
```
make clean
```
# Credits and References
* YouRock https://github.com/YouROK
* Huge thanks for https://github.com/nirev his scripts made it easier to build packages.
* Package structure https://help.synology.com/developer-guide/index.html
* Architecture per Synology model https://github.com/SynoCommunity/spksrc/wiki/Architecture-per-Synology-model
