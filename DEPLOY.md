# Deployment: GitLab → GitHub mirror

This repository lives on **GitLab** as the source of truth. A GitLab push mirror keeps a copy on **GitHub** in sync.

| Platform | Repository |
| -------- | ---------- |
| GitLab (source) | `https://gitlab.com/sandrineboissel/strava-analytics` |
| GitHub (mirror) | `https://github.com/sboissel/strava-analytics` |

GitLab CI (`.gitlab-ci.yml`) runs tests on push and a weekly scheduled sync that commits updated `data/` files back to `main`. Pushing to GitLab (including those CI commits) is enough for the mirror to update GitHub.

See the **Weekly GitLab sync** section in [README.md](README.md) for CI variables and the Sunday pipeline schedule.

## 1. Create the GitHub repository

1. On GitHub, create a repository (e.g. `sboissel/strava-analytics`).
2. Leave it empty — do not add a README, `.gitignore`, or license (GitLab will push the full history).

## 2. Configure GitLab push mirror

In GitLab (`https://gitlab.com/sandrineboissel/strava-analytics`):

1. Go to **Settings → Repository → Mirroring repositories**.
2. Under **Push to a remote repository**:
   - **Git repository URL**: `https://github.com/sboissel/strava-analytics.git`
   - **Mirror direction**: Push
   - **Authentication**: use a [GitHub personal access token](https://github.com/settings/tokens) (classic) with the `repo` scope, or a fine-grained token with **Contents: Read and write** on this repository.
   - Paste the token as the password (username is your GitHub username).
3. Enable **Only mirror protected branches** if you only want `main` mirrored.
4. Save and trigger **Update now** to verify the first push.

Alternative (SSH): use `git@github.com:sboissel/strava-analytics.git` with a deploy key added to the GitHub repo (**Settings → Deploy keys**, write access enabled).

## 3. Verify the mirror

After mirroring:

1. Push to `main` on GitLab (or wait for the mirror interval).
2. On GitHub, confirm `main` matches GitLab (latest commit SHA and history).
3. In GitLab → **Settings → Repository → Mirroring repositories**, confirm the last update succeeded with no errors.

## Keeping GitLab as source of truth

Recommended workflow:

1. Commit and push to GitLab `main`.
2. GitLab CI runs tests.
3. GitLab push mirror syncs to GitHub.

Do not push directly to GitHub unless you also merge back to GitLab, or the mirrors will diverge.

## 4. Streamlit Community Cloud

The dashboard can run publicly from the GitHub mirror without Strava API secrets (it reads committed CSVs only).

1. Sign in at [share.streamlit.io](https://share.streamlit.io) with GitHub.
2. **Create app** → **From existing repo** → `sboissel/strava-analytics`.
3. Set **Main file path** to `dashboard/streamlit_app.py`, branch `main`, Python **3.11**.
4. Leave **Secrets** empty.
5. Deploy and confirm **Metrics** (default) and **Training** load.

Requirements are installed from root [`requirements.txt`](requirements.txt) (includes `streamlit` and `plotly`). After the Sunday GitLab sync and mirror push, Streamlit Cloud redeploys with updated `data/` files.
