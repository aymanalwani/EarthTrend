# Metadata stage (protocol section 2, step 2)

Completed 2026-11-15T06:42Z, before any station temperature value was read.

- **Protocol frozen:** 2026-11-15T06:38Z.
- **Frozen file:** docs/STATION_VALIDATION_PROTOCOL.md, revision 3, SHA-256
  3219d63c639bf676f2a8c043e28b66c616de71efac3c3f9d8221acb9f1705427.
- **Why a hash and not a commit:** the user asked for no commits because the
  project will move to a new repository. The hash and time above are the
  registration record (amendment 1 in the protocol).

## Station history (section 7.1)

| Source | Finding |
|---|---|
| NOAA isd-history.csv | One location row per station. No relocation history. |
| WMO OSCAR/Surface | Not obtained. The station pages are a JavaScript application, and automated fetching returned no station content (2026-11-15). |
| Jordan Meteorological Department | Not requested. The protocol makes it optional and non-blocking. |
| GSOD observation counts | Aqaba rises from 17-20 to 23-24 observations per day in 2018, a change in hours of operation. King Hussein stays at 6-8 per day. Marka and Queen Alia stay at 22-24. |
| GSOD vs GHCN-M coordinates | Amman 778.8 m vs 766 m; Aqaba 53.3 m vs 51 m (29.612 vs 29.6333 N); Queen Alia 730 m vs 722 m. The cause, relocation or rounding, is not determined. |
| Satellite imagery and population | Not checked. The labels for Queen Alia and King Hussein stay "unverified". |

## Classification (section 10)

Unchanged from the protocol:

| Station | Classes |
|---|---|
| Amman Marka | urban |
| Queen Alia | not urban (unverified) |
| Aqaba | urban, coastal, Rift |
| King Hussein | not urban (unverified) |

These are labels only. No analysis selects stations by class.

## Data-use note found at this stage

The GSOD readme states that non-US data are exchanged under WMO Resolution 40.
Such data are for free and unrestricted non-commercial research and education
use, and must not be provided to other users.

For that reason:

- raw GSOD files stay in data/raw/stations/, which git ignores;
- outputs contain only differences and summary statistics.
