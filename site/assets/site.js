(function () {
  const cfg = window.DeviceDeckConfig || {};
  const setupLink = document.getElementById("download-setup");
  const portableLink = document.getElementById("download-portable");
  const releaseStatus = document.getElementById("release-status");
  const trustBanner = document.getElementById("trust-banner");
  const hashVerify = document.getElementById("hash-verify");
  const docLink = document.getElementById("signing-doc-link");
  const guideUrl = cfg.signingGuideUrl || "";

  const ver = cfg.currentVersion || "latest";
  if (releaseStatus) {
    releaseStatus.textContent = "Version " + ver;
  }

  if (docLink && guideUrl) {
    docLink.href = guideUrl;
  }

  function applyLink(el, url) {
    if (!el || !url) return;
    el.href = url;
  }

  applyLink(setupLink, cfg.setupUrl);
  applyLink(portableLink, cfg.portableUrl);

  if (trustBanner && cfg.authenticodeSigned === true) {
    trustBanner.className = "trust-banner trust-signed";
    trustBanner.innerHTML =
      "<h2>Authenticode-signed build</h2>" +
      "<p>This release was signed with a code-signing certificate. SmartScreen and most workplaces expect signed installers. " +
      "Always confirm the publisher name in the security prompt matches your trust policy.</p>";
  }

  if (hashVerify) {
    var hs = (cfg.sha256Setup || "").trim();
    var hp = (cfg.sha256Portable || "").trim();
    if (hs || hp) {
      var html =
        "<h2>Verify download integrity</h2>" +
        "<p class=\"small\">Compare SHA-256 after download (PowerShell: " +
        "<code>Get-FileHash -Algorithm SHA256</code> …).</p>" +
        "<dl class=\"hash-list\">";
      if (hs) {
        html += "<dt>Installer (.exe)</dt><dd><code>" + hs + "</code></dd>";
      }
      if (hp) {
        html += "<dt>Portable (.zip)</dt><dd><code>" + hp + "</code></dd>";
      }
      html += "</dl>";
      hashVerify.innerHTML = html;
      hashVerify.hidden = false;
    }
  }
})();
