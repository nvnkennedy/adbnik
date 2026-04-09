# SignPath setup for Device_Deck (you complete these steps)

**Nobody can register SignPath on your behalf.** It needs **your** email, identity checks, and **your** click to accept their terms. This file is the checklist to finish after you start at [signpath.org](https://signpath.org/).

## 1. Apply for open-source signing

1. Open **[SignPath Foundation](https://signpath.org/)** (or the product flow they link for OSS).
2. **Create an account** with an email you control.
3. **Apply** for a **free open-source** project and connect it to **this repository**:  
   `https://github.com/nvnkennedy/Device_Deck`  
   (Use your fork URL if the canonical repo name differs.)

Wait for their approval email before expecting signing to work.

## 2. Install the SignPath GitHub App

SignPath requires the **[SignPath GitHub App](https://github.com/apps/signpath)** installed on the **user or organization** that owns `Device_Deck`, with access to that repository.

Official doc: [Trusted build systems — GitHub](https://docs.signpath.io/trusted-build-systems/github).

## 3. Create project, policy, and API token (inside SignPath)

After login at SignPath:

1. Add the **trusted build system** **GitHub.com** to your SignPath organization and **link** it to your Device_Deck **SignPath project** (see their UI wizard).
2. Note these values (names vary by how you configured them):
   - **Organization ID**
   - **Project slug**
   - **Signing policy slug**
3. Create an **API token** with permission to **submit signing requests** for that project/policy.  
   Store it only as a **GitHub secret** (next section), never in git.

## 4. Add secrets to GitHub (repository settings)

In GitHub: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name            | Value                                      |
|------------------------|--------------------------------------------|
| `SIGNPATH_API_TOKEN`   | The API token from SignPath                |

Use **Variables** (non-secret) for IDs if you prefer:

| Variable name              | Example / note        |
|----------------------------|------------------------|
| `SIGNPATH_ORGANIZATION_ID` | From SignPath UI     |
| `SIGNPATH_PROJECT_SLUG`    | e.g. `device-deck`   |
| `SIGNPATH_SIGNING_POLICY_SLUG` | e.g. `release`   |

Exact slugs must match what you created in SignPath.

## 5. Wire GitHub Actions (after the build artifact exists)

Your release workflow already builds a portable ZIP and uploads it as an artifact. SignPath must receive an artifact produced by **GitHub Actions** and uploaded with **`actions/upload-artifact@v4+`** before signing.

Official action: [`signpath/github-action-submit-signing-request`](https://github.com/SignPath/github-action-submit-signing-request) (see **v2** usage).

Minimal pattern (adapt step IDs and paths to your workflow):

```yaml
- name: Upload unsigned artifact for SignPath
  id: upload-unsigned
  uses: actions/upload-artifact@v4
  with:
    name: unsigned-portable
    path: DeviceDeck_Portable_v0.1.0.zip   # must match your built file name

- name: Request SignPath signing
  uses: signpath/github-action-submit-signing-request@v2
  with:
    api-token: ${{ secrets.SIGNPATH_API_TOKEN }}
    organization-id: ${{ vars.SIGNPATH_ORGANIZATION_ID }}
    project-slug: ${{ vars.SIGNPATH_PROJECT_SLUG }}
    signing-policy-slug: ${{ vars.SIGNPATH_SIGNING_POLICY_SLUG }}
    github-artifact-id: ${{ steps.upload-unsigned.outputs.artifact-id }}
    wait-for-completion: true
    output-artifact-directory: signed
```

Then upload `signed/` contents to a **GitHub Release** if you distribute optional Windows installers. Most users install with **`pip install devicedeck`** from PyPI.

## 6. If something fails

- **Support:** [signpath.io/support](https://signpath.io/support) (from their site).
- **Docs:** [Build system integration](https://docs.signpath.io/build-system-integration), [GitHub trusted build](https://docs.signpath.io/trusted-build-systems/github).
- **Demo:** [SignPath/github-actions-demo](https://github.com/SignPath/github-actions-demo).

---

**Summary:** You must **log in to SignPath**, **approve the GitHub App**, and **paste secrets** into GitHub yourself. After that, you (or a contributor) can add the signing steps to `.github/workflows/release.yml` using the pattern above.
