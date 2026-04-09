// Paths are relative to the site root on GitHub Pages — files are served from site/downloads/.
window.DeviceDeckConfig = {
  setupUrl: "downloads/DeviceDeck_Setup_0.1.0.exe",
  portableUrl: "downloads/DeviceDeck_Portable_0.1.0.zip",
  currentVersion: "0.1.0",
  // Set true only when the files above are signed with Authenticode (see docs/WINDOWS_CODE_SIGNING.md).
  authenticodeSigned: false,
  // Optional: run scripts/compute_release_hashes.ps1 after copying files to site/downloads/
  sha256Setup: "",
  sha256Portable: "",
  signingGuideUrl:
    "https://github.com/nvnkennedy/Device_Deck/blob/master/docs/WINDOWS_CODE_SIGNING.md"
};
