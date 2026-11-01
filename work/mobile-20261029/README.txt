Rumah mobile client — 29 October 2026

The live site uses release /var/www/rumah/releases/20261029-fullheight-v1 in LXC 710.
The previous full native and mobile releases are retained.

Full-height correction, 29 October 2026:
  The automatic horizontal cut at world Y=1.5 is removed. Orbit and Top view
  use front-face rendering (See inside) to open the backs of ceilings and
  outside walls while retaining the complete vertical extent. The toggle
  restores double-sided rendering. Walk and recorded views are double-sided.
  No model positions, transforms, triangles, textures or downloads changed.
  Camera fitting samples each component and accounts for both screen axes.
  ../fullheight-20261029/ contains the prior client sources, guarded deployment
  package, and manifest. The working sources remain in this directory.

Source:
  room-viewer.js, loader-core.js, room-shell.html
  package.json and package-lock.json pin the dependencies.

Asset pipeline:
  simplify-source.mjs creates a border-locked mobile derivative from the
  original native model. It does not prune room sections or crop ownership.
  pack-phone.mjs reduces textures to 2048 pixels, quantizes attributes and
  applies Meshopt compression. It checks room sections and retained topology.
  phone-asset-report.json records sizes, hashes, and accuracy limits.

Build in the current task workspace:
  npm install
  node build.mjs

The build reads the original review metadata from ../hosting/public/, the
original model and overview from ../../outputs/, and the already-built phone
asset in public/models/. It never rewrites the original native GLB.

Tests:
  node --test loader-core.test.mjs
  node review-server.mjs
  Browser tests used the CUA browser API. QA modes in the review server simulate
  HTTP failure, truncated and stalled transfers. qa-script-failure.html is a
  local-only entry-script failure fixture. Never upload the whole public/
  folder blindly: the packagers use explicit asset lists and omit QA fixtures.

Deployment:
  package_site.py and deploy-mobile.sh record the first mobile deployment.
  prepare_web_patch.py and deploy-web-v2.sh record the startup recovery patch.
  They are historical, guarded scripts; choose a fresh release name and review
  the expected current release before a future deployment. Do not blindly rerun.

Public verification and notes are saved under ../../outputs/ with the date
2026-10-29. The user deferred physical Fold 7 / iPhone 17 checks until later.
