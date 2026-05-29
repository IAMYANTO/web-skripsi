# Graph Report - Bantuin anak magang  (2026-05-29)

## Corpus Check
- 4 files · ~5,055 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 33 nodes · 48 edges · 6 communities (4 shown, 2 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `58d1f94d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]

## God Nodes (most connected - your core abstractions)
1. `get_db_connection()` - 16 edges
2. `get_db_connection()` - 3 edges
3. `load_encodings_from_db()` - 3 edges
4. `login()` - 3 edges
5. `reload_faces()` - 2 edges
6. `activate_admin()` - 2 edges
7. `register()` - 2 edges
8. `dashboard()` - 2 edges
9. `trigger_bypass()` - 2 edges
10. `check_bypass_status()` - 2 edges

## Surprising Connections (you probably didn't know these)
- `login()` --calls--> `get_db_connection()`  [EXTRACTED]
  app.py → app.py  _Bridges community 1 → community 4_
- `register()` --calls--> `get_db_connection()`  [EXTRACTED]
  app.py → app.py  _Bridges community 1 → community 0_

## Communities (6 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.2
Nodes (6): activate_admin(), api_logs(), delete_user(), manage_users(), register(), trigger_bypass()

### Community 1 - "Community 1"
Cohesion: 0.22
Nodes (9): check_bypass_status(), dashboard(), delete_admin(), export_csv(), get_db_connection(), log_access(), profile(), update_password() (+1 more)

### Community 2 - "Community 2"
Cohesion: 0.36
Nodes (4): activate_admin(), get_db_connection(), load_encodings_from_db(), reload_faces()

## Knowledge Gaps
- **1 isolated node(s):** `web-skripsi`
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_db_connection()` connect `Community 1` to `Community 0`, `Community 4`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **What connects `web-skripsi` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._