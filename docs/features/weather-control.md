# Weather Control

## Conclusion

Weather control is not available through the current X-Plane local Web API that this repository uses today.

As of the X-Plane local Web API documentation updated on January 29, 2026, the supported remote operations cover datarefs, commands, and flight initialization or updates. Weather is mentioned only in the roadmap, not as a currently supported REST or WebSocket endpoint.

Weather control is possible in X-Plane through the native plugin SDK. The `XPLMWeather` APIs include write operations such as:

- `XPLMBeginWeatherUpdate`
- `XPLMSetWeatherAtAirport`
- `XPLMSetWeatherAtLocation`
- `XPLMEndWeatherUpdate`

Those APIs are the viable implementation path if this project needs weather control.

## Implication For This Repo

This repository cannot add weather control by extending the current Python `XPlaneHttpClient` against the stock local Web API alone.

To support weather writes, the project would need a companion X-Plane plugin that exposes a localhost bridge from the X-Plane plugin SDK to the Python and MCP layers.

## Proposed Plan

1. Add a weather abstraction in Python.
   Create a backend-neutral interface for operations such as `get_weather`, `set_weather_at_airport`, `set_weather_at_location`, and `clear_weather_override`.

2. Keep transport layers separate.
   Do not overload the current local Web API client with unsupported weather behavior.
   Introduce a separate bridge client, for example `XPlanePluginBridgeClient`, that talks to a native plugin.

3. Build a minimal X-Plane plugin bridge.
   Implement a small X-Plane plugin in C or C++ using `XPLMWeather`.
   Expose a localhost-only API from the plugin, preferably simple HTTP or WebSocket.

4. Start with airport-scoped weather control.
   The first supported write operation should be `set_weather_at_airport(icao, profile)` because it is simpler to validate than arbitrary spatial weather edits.

5. Define a narrow initial weather schema.
   Keep the first payload small and explicit:
   airport ICAO, visibility, cloud layers, wind direction and speed, altimeter or QNH, and precipitation state.

6. Add MCP-facing weather operations on top of the bridge.
   Candidate tool surface:
   `weather_get_current`
   `weather_set_airport`
   `weather_set_location`
   `weather_clear_override`

7. Add live integration coverage.
   Unit tests should mock the plugin bridge.
   Integration tests should run only when X-Plane and the plugin are active, and must verify that weather state actually changed in the simulator.

8. Document operational constraints.
   The X-Plane SDK weather APIs are currently experimental.
   The plugin implementation must follow SDK timing constraints for weather updates.
   This feature requires native plugin code in addition to Python.

## Suggested Repo Shape

If this feature is pursued later, the likely structure is:

```text
docs/features/weather-control.md
tests/weather_client.py
tests/weather_bridge_client.py
plugins/xplane-weather-bridge/
tests/test_weather_client.py
tests/test_weather_integration.py
```

## References

- X-Plane local Web API: https://developer.x-plane.com/article/x-plane-web-api/
- X-Plane Flight Initialization API: https://developer.x-plane.com/article/flight-initialization-api/
- XPLMWeather SDK: https://developer.x-plane.com/sdk/XPLMWeather/
- XPLMSetWeatherAtAirport: https://developer.x-plane.com/sdk/XPLMSetWeatherAtAirport/
- XPLMSetWeatherAtLocation: https://developer.x-plane.com/sdk/XPLMSetWeatherAtLocation/
- XPLMEndWeatherUpdate: https://developer.x-plane.com/sdk/XPLMEndWeatherUpdate/
