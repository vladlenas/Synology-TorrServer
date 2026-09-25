# TorrServer package for Synology NAS

Synology NAS package for DSM 7.3 and newer, based on TorrServer binaries:

https://github.com/YouROK/TorrServer/releases

You can thank the TorrServer developer here:

https://github.com/YouROK/TorrServer#donate

# Supported Architecture

* arm7 - alpine alpine4k armada38x monaco
* arm64 - aarch64 armv8 rtd1296 armada37xx rtd1619b
* amd64 - apollolake avoton braswell broadwell broadwellnk broadwellnkv2 broadwellntbap bromolow denverton epyc7002 geminilake grantley kvmx64 purley r1000 v1000 x86_64

DSM versions below 7.3 and the following architectures are not supported:

* 386 / evansport
* ARMv5

# Automatic update

Add https://grigi.lt/ to your Synology NAS Package Center sources!

# Making packages from precompiled TorrServer binaries

```bash
git clone https://github.com/vladlenas/Synology-TorrServer.git
cd Synology-TorrServer/
```

```bash
make
```

TorrServer version and package version can be changed in `Makefile`:

```make
TORRSERVER_VERSION := MatriX.143
PKG_VERSION := 1.2.143
DSM := 7.3
```

# Clear working directory

```bash
make clean
```

# Log file

```text
/var/packages/TorrServer/var/TorrServer.log
/var/log/packages/TorrServer.log
```

# Permission DSM 7.3 for write cache to hard drive

* `Control Panel > Shared Folder > Select Shared Folder > Edit > Permissions > System internal user > TorrServer user > Read/Write`

# Credits and References

* YouROK: https://github.com/YouROK
* TorrServer: https://github.com/YouROK/TorrServer
* SynoCommunity: https://github.com/SynoCommunity/spksrc
* Synology DSM Developer Guide: https://help.synology.com/developer-guide/
* Architecture per Synology model: https://github.com/SynoCommunity/spksrc/wiki/Architecture-per-Synology-model
