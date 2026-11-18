// Local configuration, mounted as config.js by docker compose.
// On Azure, the pipeline generates config.js with the deployed services' URLs instead.
window.TRIPSYNC_CONFIG = {
  SCHEDULING_URL: "http://localhost:8001",
  TRIPS_URL: "http://localhost:8002",
};
