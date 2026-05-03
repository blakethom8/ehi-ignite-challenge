# Pinned SHAs — Josh Mandel Stack Deep Dive

All four core repos cloned `--depth=1` to `/tmp/josh-stack/` on 2026-05-01. Future sessions read against these exact commits — if they drift, re-clone but record the new SHA in this file with a dated entry.

| Repo | SHA | Last commit (UTC) | Subject |
|---|---|---|---|
| `health-skillz` | `a7fd8acf8cb076704ab038d37de7c691c2f04e84` | 2026-03-13 04:33 | "Two keys in order" |
| `health-record-mcp` | `e4b03bd1c04f335fb0681828231cfd303c0aa492` | 2025-08-14 23:26 (-0500) | Merge PR #4 (`copilot/fix-2`) |
| `my-health-data-ehi-wip` | `188d93814515636afd9f027f2d5efebfd00260c7` | 2026-01-02 20:51 (-0800) | Merge PR #13 (`copilot/fix-open-router-api-calls`) |
| `request-my-ehi` | `fd0a8cd8356d067b8927328ec778b3149b194b3d` | 2026-03-02 16:10 | "Add skill downloads to dashboard charts" |

**Re-clone command:**

```bash
mkdir -p /tmp/josh-stack && cd /tmp/josh-stack
for r in health-skillz health-record-mcp my-health-data-ehi-wip request-my-ehi; do
  git clone --depth=1 https://github.com/jmandel/$r.git
done
```

To pin to a specific SHA after cloning at depth=1, fetch and reset:

```bash
cd /tmp/josh-stack/health-skillz
git fetch --depth=1 origin a7fd8acf8cb076704ab038d37de7c691c2f04e84
git checkout a7fd8acf8cb076704ab038d37de7c691c2f04e84
```

## Reference-tier repos (not yet cloned)

These can be pulled later if a session needs them:

- `jmandel/sample_ccdas` — CC BY 4.0 data corpus, 747 CCDA fixtures, 2018-frozen.
- `jmandel/ehi-export-analysis` — 219 vendor product abstractions; drives `request-my-ehi`'s Appendix A.
- `jmandel/write-clinical-notes.skill` — second Anthropic-format skill (different domain).

## Update history

- **2026-05-01** — initial clone; all four core repos pinned.
