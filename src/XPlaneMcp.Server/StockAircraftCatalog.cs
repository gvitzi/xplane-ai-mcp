namespace XPlaneMcp.Server;

/// <summary>
/// Hardcoded relative paths (from the X-Plane install root) for Laminar stock aircraft in X-Plane 12,
/// for use with the flight API <c>aircraft.path</c> field. Does not scan the filesystem.
/// </summary>
internal static class StockAircraftCatalog
{
    /// <summary>Ordered list suitable for MCP JSON (Name, Path).</summary>
    public static IReadOnlyList<XPlaneAircraftModel> All { get; } =
    [
        new("Aero-Works Aerolite 103", "Aircraft/Laminar Research/Aero-Works Aerolite 103/Aerolite_103.acf"),
        new("Airbus A330-300", "Aircraft/Laminar Research/Airbus A330-300/A330.acf"),
        new("Beechcraft Baron 58", "Aircraft/Laminar Research/Beechcraft Baron 58/Baron_58.acf"),
        new("Beechcraft King Air C90B", "Aircraft/Laminar Research/Beechcraft King Air C90B/C90B.acf"),
        new("Boeing 737-800", "Aircraft/Laminar Research/Boeing 737-800/b738.acf"),
        new("Cessna 172 SP", "Aircraft/Laminar Research/Cessna 172 SP/Cessna_172SP.acf"),
        new("Cessna 172 SP G1000", "Aircraft/Laminar Research/Cessna 172 SP G1000/Cessna_172SP_G1000.acf"),
        new("Cessna 172 (tow / legacy)", "Aircraft/Laminar Research/Cessna 172/C172.acf"),
        new("Cessna Citation X", "Aircraft/Laminar Research/Cessna Citation X/CitationX.acf"),
        new("Cirrus SR22", "Aircraft/Laminar Research/Cirrus SR22/SR22.acf"),
        new("Cirrus Vision SF50", "Aircraft/Laminar Research/Cirrus Vision SF50/SF50.acf"),
        new("Grumman F-14 Tomcat", "Aircraft/Laminar Research/Grumman F-14 Tomcat/F-14.acf"),
        new("Lancair Evolution", "Aircraft/Laminar Research/Lancair Evolution/EVO.acf"),
        new("McDonnell Douglas F-4 Phantom II", "Aircraft/Laminar Research/F-4 Phantom II/F-4.acf"),
        new("McDonnell Douglas MD-82", "Aircraft/Laminar Research/McDonnell Douglas MD-82/MD-82.acf"),
        new("Piper PA-18 Super Cub", "Aircraft/Laminar Research/Piper PA-18 Super Cub/PA18.acf"),
        new("Robinson R22 Beta II", "Aircraft/Laminar Research/Robinson R22 Beta II/R22.acf"),
        new("Schleicher ASK 21", "Aircraft/Laminar Research/Schleicher ASK 21/ASK21.acf"),
        new("Sikorsky S-76", "Aircraft/Laminar Research/Sikorsky S-76/S76.acf"),
        new("Stinson L-5 Sentinel", "Aircraft/Laminar Research/Stinson L-5 Sentinel/L5.acf"),
        new("Van's Aircraft RV-10", "Aircraft/Laminar Research/Van's Aircraft RV-10/RV-10.acf"),
    ];
}
