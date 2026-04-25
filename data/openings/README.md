# Opening books

EPD files used by external UCI front-ends (e.g.
[`cutechess-cli`](https://github.com/cutechess/cutechess)) to inject
opening positions when running engine-vs-engine matches. They are
**not** consumed by anything in this repo's own Python code — only by
the external tournament harness when you launch one of the head-to-head
matches in `reports/head_to_head/`.

## Files

| file                  | size  | status       | notes                                                                                                                  |
|-----------------------|-------|--------------|------------------------------------------------------------------------------------------------------------------------|
| `8mvs_+90_+99.epd`    | 569 K | **active**   | 8-move book biased to balanced openings (eval between +90 and +99 cp). This is the book that produced every match in `reports/head_to_head/`. |
| `3moves_FRC.epd`      | 8.0 M | unused       | Fischer Random Chess (Chess960) opening book, 3-move depth. Kept around in case we ever run a 960 head-to-head; safe to delete if not needed. |
| `Pohl.epd`            | 14 B  | **broken**   | Literal contents are the string `404: Not Found` — a botched download. Kept here only so the directory listing matches what was previously at the repo root; safe to delete. |

## Re-running a head-to-head with these books

Every summary log in `reports/head_to_head/` records the exact opening
book used (look for the `... .epd):` line in the file). To re-run a
match with cutechess-cli, point `-openings file=...` at the file in
this directory:

```bash
cutechess-cli \
  -engine cmd=infra/uci_launchers/rlm.sh        proto=uci \
  -engine cmd=infra/uci_launchers/langgraph.sh  proto=uci \
  -openings file=data/openings/8mvs_+90_+99.epd format=epd order=random \
  -each tc=10+0.1 \
  -rounds 5 -repeat -concurrency 1
```
