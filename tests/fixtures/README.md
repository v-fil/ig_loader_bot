# Test fixtures

Live HTTP responses captured from the scraped services on **2026-06-12** with
`capture.py` (see its docstring for re-capture usage). Bodies only — no
cookies; Meta's embedded anonymous-session tokens (`csrf_token`, `device_id`,
LSD) are redacted by the capture script.

| File | Source | What it is |
| --- | --- | --- |
| `fastdl_ajax_search.json` | instagram.com/p/Cf4_rZ8jz5z (NASA Webb's First Deep Field, @jameswebb_nasa) | fastdown.to `ajaxSearch` response; `data` holds the obfuscated JS payload that `FastDLSessionStrategy` runs through dukpy. Decodes to one image link. **The payload self-expires**: it only writes its result while `(+new Date())/1000` is below a timestamp embedded at capture time (hours of validity), so `test_fastdl.py` shims `Date` to the capture date before replaying it. |
| `threads_post.html` | threads.com/@zuck/post/DPCXhCwkqEe | Post page with embedded `data-sjs` JSON. Unrolls to a 3-post OP chain, text on all posts, 5 carousel images on post 2. |
| `threads_post_op_not_leading.html` | threads.com/@zuck/post/DTTnkzwkdSx | Real-world failure shape: the OP post never *leads* a `thread_items` array (it appears mid-array after a quoting reply), so `_unroll` yields nothing and the strategy returns `None`. Kept for a future regression test if `_unroll` learns this shape. |
| `fxtwitter_status.json` | twitter.com/TheEllenShow/status/440322224407314432 | fxtwitter API response for a photo tweet (`tweet.media.all` with one `photo`). |
| `snaptik_page.html` | snaptik.pro landing page | Contains the hidden `token` input the strategy extracts. |
| `snaptik_action.json` | tiktok.com/@zachking/video/6768504823336815877 | snaptik.pro `/action` response; `html` contains the download link in the `btn-container` div. |

These sites change without notice. When a strategy breaks against the live
site, refresh its fixture (`.venv/bin/python tests/fixtures/capture.py <name>`)
before trusting the tests.
