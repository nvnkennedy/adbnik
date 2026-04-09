(function () {
  const cfg = window.DeviceDeckConfig || {};
  const setupLink = document.getElementById("download-setup");
  const portableLink = document.getElementById("download-portable");
  const releaseStatus = document.getElementById("release-status");

  const ver = cfg.currentVersion || "latest";
  if (releaseStatus) {
    releaseStatus.textContent = "Version " + ver;
  }

  function applyLink(el, url, filename) {
    if (!el || !url) return;
    el.href = url;
    if (filename) {
      el.setAttribute("download", filename);
    }
  }

  applyLink(setupLink, cfg.setupUrl, "DeviceDeck_Setup_" + ver + ".exe");
  applyLink(portableLink, cfg.portableUrl, "DeviceDeck_Portable_" + ver + ".zip");
})();
