from pathlib import Path
import json,hashlib
w=Path(__file__).parent
out=w.parent.parent/'outputs'
phone=json.loads((w/'phone-asset-report.json').read_text())
build=json.loads((w/'build-report.json').read_text())
tests=json.loads((w/'browser-verification.json').read_text())
digest=hashlib.sha256((w/'public-phone.glb').read_bytes()).hexdigest()
assert digest==phone['sha256']
assert next(t for t in tests if t['test']=='final-v2-public-render')['phase']=='ready'
assert next(t for t in tests if t['test']=='stalled-download-45s-recovery')['phase']=='failed'
assert next(t for t in tests if t['test']=='partial-download-recovery')['phase']=='failed'
assert next(t for t in tests if t['test']=='full-native-remains-available')['triangles']==11891853
first=next(t for t in tests if t['test']=='public-https-first-phone-load')
report={
 'date':'2026-10-29','site':'https://rumah.shizuku.rest/',
 'phone_link':'https://rumah.shizuku.rest/?quality=phone&v=20261029',
 'release':'/var/www/rumah/releases/20261029-mobile-v2','lxc':710,
 'changes':['Automatic phone delivery, including touch devices at wide unfolded sizes','Bounded texture and geometry budgets','Streaming download progress','Timeout and retry UI for stalled, truncated, or failed downloads','Entry-script startup watchdog and a direct photo fallback','Pinch zoom, two-finger pan and walking buttons','Original native model remains available without geometry or texture changes'],
 'phone_asset':phone,'http_transfer_bytes':17853120,'old_http_transfer_bytes':302564257,
 'anonymous_public_download_sha256':digest,'public_http_status':200,
 'desktop_phone_view_first_public_load_seconds':first['preparedSeconds'],
 'phone_sized_viewports_tested':[[402,874],[884,796]],
 'touch_walk_hold_release':{'held_milliseconds':600,'camera_moved':True,'active_moves_after_release':[],'keys_after_release':[]},
 'automated_loader_checks':{'passed':7,'failed':0},
 'browser_checks':tests,
 'screenshots':['Rumah_Phone_View_2026-10-29.jpg','Rumah_Unfolded_View_2026-10-29.jpg'],
 'physical_device_confirmation':{'Fold 7':'pending','iPhone 17':'pending','user_reply':'I will check later'},
 'root_cause_observations':['Previous default sent every visitor the 435.6 MB native GLB, about 302.6 MB over HTTP gzip','Previous UI gave no transfer progress or stall deadline','An iPhone request in the server log ended after about 63.3 MB, before the compressed file completed'],
 'cause_not_proven':'No phone crash trace was captured; memory pressure is plausible and addressed, but was not diagnosed from the server log alone.',
 'rollback':'Point /var/www/rumah/current back to /var/www/rumah/releases/20261027-full-native; both earlier releases are retained.',
 'build':build
}
(out/'Rumah_Mobile_Verification_2026-10-29.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
note=f'''RUMAH PHONE LOADING UPDATE — 29 OCTOBER 2026

Fresh phone link: https://rumah.shizuku.rest/?quality=phone&v=20261029
Close an old stuck tab before opening this link on a phone.

The update is live in Proxmox LXC 710. Phones automatically receive a smaller
3D view; the full native model remains available in the quality selector and
through Download original. There is no password.

PHONE VIEW
GLB file: 21,144,604 bytes; HTTP gzip transfer: 17,853,120 bytes.
Geometry: 1,603,164 triangles across the original two room sections.
Textures: two 2048 x 2048 JPEG images.
The phone view is a reduced-detail derivative. It does not claim independently
verified 2 mm accuracy. It retains mesh borders and does not apply ownership
cropping or discard a room section.
The original full native model is unchanged:
435,614,584 bytes; 11,891,853 triangles; two 8192 x 8192 textures.
Native SHA-256: 16f8963b043a766317497ee4281f4cf39c6b2190fafaaed51334734723c8b207

LOADING AND CONTROLS
The page shows actual download progress followed by preparation/drawing stages.
A connection that stops sending data gets a retry message after 45 seconds.
The phone download has a three-minute total limit, and preparation/drawing
also have deadlines. A missing viewer script has a startup watchdog.
Photos remain available if 3D cannot open. Graphics-context loss produces a
visible retry message. The phone view adds pinch zoom, two-finger pan, zoom
buttons and walking arrows. Layout adjusts to portrait and unfolded screens.

VERIFICATION
The public phone GLB downloaded anonymously over HTTPS with status 200 and
matched SHA-256 {digest}.
The first public 3D load in desktop Chrome at a phone-sized viewport completed
in {first['preparedSeconds']:.2f} seconds on the test connection. This is not a phone
hardware benchmark. Both 402 x 874 and 884 x 796 layouts rendered successfully.
Recorded camera/source-photo comparison and walking-button movement/release
were checked. Seven loader checks passed. The UI was tested with a missing
model, a truncated transfer, a stalled transfer, and a missing entry script.
The full native rendering option was also checked.

Actual Fold 7 and iPhone 17 confirmation is pending. The user will check later.

CAUSE AND LIMITS
The previous page requested the large native model on phones without download
progress or a stall deadline. A server log showed an iPhone transfer ending
before the whole file arrived. No phone crash trace was captured, so this
does not establish memory exhaustion as the exact cause. The update reduces
both network demand and graphics memory while exposing recoverable errors.

DEPLOYMENT
Live release: /var/www/rumah/releases/20261029-mobile-v2
Current symlink: /var/www/rumah/current
Private deployment staging: /var/lib/vz/rumah-deploy/20261029-mobile
Earlier full-native and first mobile releases remain available for rollback.
Nginx and Cloudflare Tunnel remain active. No tunnel, DNS or password changes
were needed. Local QA failure pages were not deployed publicly.
'''
(out/'Rumah_Mobile_Update_2026-10-29.txt').write_text(note,encoding='utf-8')
print('Saved mobile update notes and verification evidence. Physical phone confirmation is pending.')
