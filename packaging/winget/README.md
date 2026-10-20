# winget manifests

These files let people install Mixie with:

```
winget install Modda-ctrl.Mixie
```

They are submitted to [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs) under
`manifests/m/Modda-ctrl/Mixie/<version>/`.

**For a new version:** copy the folder, change `PackageVersion`, `ReleaseDate`, `InstallerUrl` and
`InstallerSha256` (the `Mixie.exe` line in the release's `SHA256SUMS.txt`, in capital letters), then submit.
The easiest way is Microsoft's tool, which fills in everything from the download link:

```
winget install Microsoft.WingetCreate
wingetcreate update Modda-ctrl.Mixie --version X.Y.Z --urls https://github.com/Modda-ctrl/Mixie/releases/download/vX.Y.Z/Mixie.exe --submit
```
