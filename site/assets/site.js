(function () {
  const cfg = window.DeviceDeckConfig || {};
  const setupLink = document.getElementById("download-setup");
  const portableLink = document.getElementById("download-portable");
  const releaseStatus = document.getElementById("release-status");

  if (setupLink) setupLink.href = cfg.setupUrl || "#";
  if (portableLink) portableLink.href = cfg.portableUrl || "#";
  if (releaseStatus) releaseStatus.textContent = `Current version: ${cfg.currentVersion || "latest"}`;
})();
