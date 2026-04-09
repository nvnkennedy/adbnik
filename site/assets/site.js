(function () {
  const cfg = window.DeviceDeckConfig || {};
  const owner = cfg.owner || "YOUR_USER";
  const repo = cfg.repo || "YOUR_REPO";
  const base = `https://github.com/${owner}/${repo}`;
  const latest = `${base}/releases/latest`;
  const apiLatest = `https://api.github.com/repos/${owner}/${repo}/releases/latest`;

  const setupLink = document.getElementById("download-setup");
  const portableLink = document.getElementById("download-portable");
  const releaseLink = document.getElementById("download-release");
  const releaseStatus = document.getElementById("release-status");

  // Safe fallback links if API lookup fails or owner/repo is not configured yet.
  if (setupLink) setupLink.href = latest;
  if (portableLink) portableLink.href = latest;
  if (releaseLink) {
    releaseLink.href = latest;
  }

  const repoLinks = document.querySelectorAll("[data-repo-link]");
  repoLinks.forEach((el) => {
    el.href = base;
  });

  fetch(apiLatest)
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("latest-release-unavailable"))))
    .then((data) => {
      if (!data || !Array.isArray(data.assets)) return;
      if (releaseStatus && data.tag_name) {
        releaseStatus.textContent = `Latest version: ${data.tag_name}`;
      }
      const setup = data.assets.find((a) => typeof a.name === "string" && /^DeviceDeck_Setup_.*\.exe$/i.test(a.name));
      const portable = data.assets.find(
        (a) => typeof a.name === "string" && /^DeviceDeck_Portable_.*\.zip$/i.test(a.name)
      );
      if (setup && setup.browser_download_url && setupLink) {
        setupLink.href = setup.browser_download_url;
      }
      if (portable && portable.browser_download_url && portableLink) {
        portableLink.href = portable.browser_download_url;
      }
    })
    .catch(() => {
      // Keep fallback latest release page links.
      if (releaseStatus) {
        releaseStatus.textContent = "Latest version link unavailable right now. Please open Releases.";
      }
    });
})();
