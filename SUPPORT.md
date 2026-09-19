# Support

This is a portfolio project maintained by one person. There is no SLA, no
support rotation and no guarantee of a reply — but issues are read.

**Before opening anything, try `make demo`.** It renders a real MP4 with no API
key and no network. If it works, your problem is configuration or credentials;
if it fails, the failure is in the project and worth reporting.

| What you have | Where it goes |
|---|---|
| It crashes, or produces something obviously wrong | GitHub issue — bug template. Include the exact command, the traceback, and `python -V` |
| A document is wrong or out of date | GitHub issue — docs template. This is the most useful report you can file here |
| An idea for what it should do | GitHub issue — feature template |
| A credential, scraping or licensing concern | [SECURITY.md](SECURITY.md) |
| You want to change the code | [CONTRIBUTING.md](CONTRIBUTING.md) |

Things that are already known and are not bugs: platform export raises
`NotImplementedError`, character and vector features need the extras in
`requirements-vector.txt`, and Python outside 3.11–3.12 will not install. All
three are documented in the [README](README.md).

Reading order if you are trying to understand the system rather than run it:
[docs/architecture.md](docs/architecture.md), then
[docs/adr/](docs/adr/).
