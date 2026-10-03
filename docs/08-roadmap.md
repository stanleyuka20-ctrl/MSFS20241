# 08 — Release plan

Each release is a separately installable package for a contiguous district,
expanding from verified areas and prioritising routes that connect completed
districts. A release ships only what its evidence supports.

| Release | Content | Exit criteria |
|---|---|---|
| **R0** (this) | Toolchain, inventory model, geometry generator, checks, telemetry analyser, coverage reporting, docs; demo route defined | Offline tests pass (done). No in-game claims |
| **R1** | Demo route on the simulator host: G0 host inspection, V1–V12 verification, vehicle decision, Gate G1 (D1–D10). Generate flatten/exclusion polygons once V8/V9 schema confirmed | Demo segments `verified`; verification register filled in |
| **R2** | Greenpoint + Long Island City + Williamsburg/Lower East Side; Williamsburg, Manhattan and Brooklyn bridges; visual LODs (after V11); textures for asphalt/concrete/markings/curbs | All in-scope segments `verified` or individually `blocked` |
| **R3** | Lower/Midtown Manhattan grid; Queensboro Bridge (both levels); Roosevelt Island; Kosciuszko, Greenpoint Ave, Grand St bridges | As above; multi-level decks verified level-by-level |
| **R4** | Upper Manhattan, South Bronx, Randalls Island (RFK), Whitestone, Throgs Neck; Brooklyn/Queens expansion; Verrazzano + Staten Island north shore | As above |
| **R5** | Harlem River crossings, GWB + NJ extension, Henry Hudson / Alexander Hamilton; remaining Bronx | As above, extension cut documented |
| **R6** | Remaining Queens (incl. Rockaways), Brooklyn south, Staten Island | As above |
| **R7** | Citywide consolidation; secondary features (traffic, navigation) only after all driving routes are reliable | 100 % of in-scope km `verified` or individually justified as `blocked` |

Tunnels run as a parallel feasibility track (data/tunnels.json); they are not
on the critical path.
