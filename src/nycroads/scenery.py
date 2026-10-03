"""MSFS package content: model-library XML and scenery placement XML.

Element/attribute names follow the MSFS SDK scenery XML format as used by the
SDK's sample scenery projects (``FSData`` / ``SceneryObject`` / ``LibraryObject``
and ``ModelInfo`` / ``LODS`` / ``LOD``). They are marked UNVERIFIED for MSFS 2024
in docs/02-technical-approach.md and must be diffed against an XML file saved by
the installed SDK's Scenery Editor before a release build (tools/verify_sdk_formats.md).

GUIDs are UUIDv5 values derived from tile IDs, so regenerating never changes them.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from xml.sax.saxutils import quoteattr

PROJECT_NS = uuid.UUID("6f1c2b8e-3d4a-5e6f-8a9b-0c1d2e3f4a5b")


def model_guid(name: str) -> str:
    return "{" + str(uuid.uuid5(PROJECT_NS, name)).upper() + "}"


def model_info_xml(name: str, lods: list[tuple[str, float]]) -> str:
    """``lods``: [(gltf_file_name, minSize)], most detailed first."""
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<ModelInfo guid="{model_guid(name)}" version="1.1">',
        "    <LODS>",
    ]
    for f, min_size in lods:
        lines.append(f'        <LOD minSize="{min_size:g}" ModelFile={quoteattr(f)}/>')
    lines += ["    </LODS>", "</ModelInfo>", ""]
    return "\n".join(lines)


def placement_xml(objects: list[dict]) -> str:
    """``objects``: [{name, lat, lon, alt_m, heading}] with alt_m in the simulator's MSL reference.

    Placement uses absolute altitude (altitudeIsAgl=FALSE) and no snapping: road
    heights are computed by the pipeline and must not follow the terrain mesh.
    """
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<FSData version="9.0">']
    for o in objects:
        lines.append(
            f'    <SceneryObject displayName={quoteattr(o["name"])} lat="{o["lat"]:.9f}" lon="{o["lon"]:.9f}" '
            f'alt="{o["alt_m"]:.3f}" pitch="0.000000" bank="0.000000" heading="{o.get("heading", 0.0):.6f}" '
            f'imageComplexity="VERY_SPARSE" altitudeIsAgl="FALSE" snapToGround="FALSE" snapToNormal="FALSE">')
        lines.append(f'        <LibraryObject name="{model_guid(o["name"])}" scale="1.000000"/>')
        lines.append("    </SceneryObject>")
    lines += ["</FSData>", ""]
    return "\n".join(lines)


def write_package_content(package_root: Path, package_name: str, tiles: list[dict]) -> list[Path]:
    """Write model-library XMLs and the placement XML into PackageSources.

    ``tiles``: [{name, gltf (Path), lat, lon, alt_m}]
    """
    src = package_root / "PackageSources"
    lib = src / "modelLib" / package_name
    scene = src / "scene"
    lib.mkdir(parents=True, exist_ok=True)
    scene.mkdir(parents=True, exist_ok=True)
    for f in list(lib.glob(f"{package_name}-*")) + [scene / f"{package_name}.xml"]:
        if f.exists():
            f.unlink()                           # remove previous build's generated files
    written = []
    for t in tiles:
        g = Path(t["gltf"])
        for f in (g, g.with_suffix(".bin")):
            if f.exists():
                dst = lib / f.name
                dst.write_bytes(f.read_bytes())
                written.append(dst)
        x = lib / f"{t['name']}.xml"
        x.write_text(model_info_xml(t["name"], [(g.name, 0)]))
        written.append(x)
    p = scene / f"{package_name}.xml"
    p.write_text(placement_xml(tiles))
    written.append(p)
    return written


def write_project_files(package_root: Path, package_name: str, title: str) -> list[Path]:
    """Baseline project + package-definition XML (MSFS SDK project format as used by the SDK
    scenery samples). UNVERIFIED for MSFS 2024 (verification item V1): existing files are
    left untouched so a version corrected against the installed SDK is never overwritten."""
    proj = package_root / f"{package_name}.xml"
    pdef = package_root / "PackageDefinitions" / f"{package_name}.xml"
    ci = package_root / "PackageDefinitions" / package_name / "ContentInfo"
    ci.mkdir(parents=True, exist_ok=True)
    out = []
    if not proj.exists():
        proj.write_text(f"""<?xml version="1.0" encoding="utf-8"?>
<!-- BASELINE project file (MSFS SDK project format of the SDK scenery samples).
     STATUS: UNVERIFIED for MSFS 2024 (V1). Diff against a project created by the installed
     SDK's Project Editor and keep the SDK's version (this file is then never regenerated). -->
<Project Version="2" Name="{package_name}" FolderName="Packages">
    <OutputDirectory>.</OutputDirectory>
    <TempOutputDirectory>_PackageInt</TempOutputDirectory>
    <Packages>
        <Package>PackageDefinitions\\{package_name}.xml</Package>
    </Packages>
</Project>
""".replace("\\\\", "\\"))
        out.append(proj)
    if not pdef.exists():
        pdef.write_text(f"""<?xml version="1.0" encoding="utf-8"?>
<!-- BASELINE package definition. STATUS: UNVERIFIED for MSFS 2024 (V1). -->
<AssetPackage Version="0.1.0">
    <ItemSettings>
        <ContentType>SCENERY</ContentType>
        <Title>{title}</Title>
        <Manufacturer>NYC Drivable Roads project</Manufacturer>
        <Creator>nycroads</Creator>
    </ItemSettings>
    <Flags>
        <VisibleInStore>false</VisibleInStore>
        <CanBeReferenced>false</CanBeReferenced>
    </Flags>
    <AssetGroups>
        <AssetGroup Name="ContentInfo">
            <Type>ContentInfo</Type>
            <Flags>
                <FSXCompatibility>false</FSXCompatibility>
            </Flags>
            <AssetDir>PackageDefinitions\\{package_name}\\ContentInfo\\</AssetDir>
            <OutputDir>ContentInfo\\{package_name}\\</OutputDir>
        </AssetGroup>
        <AssetGroup Name="{package_name}-modelLib">
            <Type>ModelLib</Type>
            <Flags>
                <FSXCompatibility>false</FSXCompatibility>
            </Flags>
            <AssetDir>PackageSources\\modelLib\\{package_name}\\</AssetDir>
            <OutputDir>scenery\\nycroads\\{package_name}-modelLib\\</OutputDir>
        </AssetGroup>
        <AssetGroup Name="{package_name}-scene">
            <Type>BGL</Type>
            <Flags>
                <FSXCompatibility>false</FSXCompatibility>
            </Flags>
            <AssetDir>PackageSources\\scene\\</AssetDir>
            <OutputDir>scenery\\nycroads\\{package_name}-scene\\</OutputDir>
        </AssetGroup>
    </AssetGroups>
</AssetPackage>
""".replace("\\\\", "\\"))
        out.append(pdef)
    return out
