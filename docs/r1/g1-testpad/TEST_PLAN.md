# Driving test plan - g1-testpad

Generated from build `B20261003T075829Z` by `nycroads test-plan`. Coordinates are WGS84; heights are the generated road surface in the current simulator height reference (UNVERIFIED until V7 calibration).

## D1

**Do:** spawn and wait 10 s

```json
{
 "start": {
  "lat": 40.5930147,
  "lon": -73.8955361,
  "heading_deg": 90.0,
  "surface_alt_m": 3.92
 },
 "segment": "SEG-5a2eadf48a",
 "name": "Testpad Main"
}
```

## D2

**Do:** accelerate to ~40 km/h along the street, brake to a stop before its end

```json
{
 "start": {
  "lat": 40.5930147,
  "lon": -73.8955361,
  "heading_deg": 90.0,
  "surface_alt_m": 3.92
 },
 "segments": [
  "SEG-5a2eadf48a"
 ],
 "length_m": 120.0
}
```

## D4

**Do:** from the D2 stop, reverse 30 m

```json
{
 "segments": [
  "SEG-5a2eadf48a"
 ]
}
```

## D3

**Do:** approach the intersection on every arm in its permitted direction; turn left, right and go straight from each

```json
{
 "junction": "JCT-d1a0d9c794",
 "lat": 40.5930158,
 "lon": -73.8956542,
 "arms": [
  {
   "segment": "SEG-2bb7307404",
   "name": "Testpad Main",
   "oneway": "both"
  },
  {
   "segment": "SEG-5a2eadf48a",
   "name": "Testpad Main",
   "oneway": "both"
  },
  {
   "segment": "SEG-e89ad91427",
   "name": "Testpad Cross",
   "oneway": "both"
  },
  {
   "segment": "SEG-d95a6777cd",
   "name": "Testpad Cross",
   "oneway": "both"
  }
 ]
}
```

## D5

**Do:** start below the steep part, stop on it, hold 10 s with brakes, release, hill start

```json
{
 "segment": "SEG-428ba0402c",
 "name": "Testpad Bridge",
 "max_grade": 0.081,
 "stop_point": {
  "lat": 40.5929802,
  "lon": -73.8919322,
  "heading_deg": 270.0,
  "surface_alt_m": 7.84
 }
}
```

## D6

**Do:** start ~150 m before the deck on its approach, drive approach -> deck -> exit without stopping, then repeat with a stop on the steepest part

```json
{
 "crossing": "Testpad Bridge",
 "runs": [
  {
   "deck": "BRG-580df1189f",
   "segment": "SEG-428ba0402c",
   "direction": "forward",
   "deck_start": {
    "lat": 40.5929977,
    "lon": -73.8937637,
    "heading_deg": 90.0,
    "surface_alt_m": 3.97
   },
   "crown_alt_m": 8.89
  },
  {
   "deck": "BRG-580df1189f",
   "segment": "SEG-428ba0402c",
   "direction": "backward",
   "deck_start": {
    "lat": 40.5929734,
    "lon": -73.8912233,
    "heading_deg": 270.0,
    "surface_alt_m": 3.84
   },
   "crown_alt_m": 8.89
  }
 ]
}
```

## D7

**Do:** drive beneath the structure in each permitted direction

```json
{
 "grade_separation": "GSX-6776c76fe4",
 "lower": "SEG-5745db4b01",
 "lower_name": "Testpad Underpass",
 "upper": "SEG-428ba0402c",
 "upper_name": "Testpad Bridge",
 "start": {
  "lat": 40.5926678,
  "lon": -73.8922328,
  "heading_deg": 0.0,
  "surface_alt_m": 3.85
 },
 "all_candidates": [
  "GSX-6776c76fe4"
 ]
}
```

## D9

**Do:** one continuous recording of >= 20 min covering D2-D8 with no recovery

## D10

**Do:** restart the simulator; repeat D3, D6 and D7 with `--after-restart`
