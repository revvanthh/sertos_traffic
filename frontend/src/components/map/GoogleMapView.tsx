import { useEffect, useRef, useState } from "react";
import { importLibrary } from "@googlemaps/js-api-loader";
import { getGoogleMapsApiKey } from "../../config/env";
import type {
  HospitalMarkerData,
  LatLng,
  MapIncidentMarker,
  PoliceUnit,
  TrackedAmbulance,
  TrafficSignal,
} from "../../types/police";
import { BENGALURU_CENTER } from "../../data/bengaluruDemoData";

export interface GoogleMapViewProps {
  center?: LatLng;
  zoom?: number;
  realLocation?: LatLng | null;
  realAccuracyMeters?: number | null;
  isRealLocationActive?: boolean;
  followRealLocation?: boolean;
  ambulances: TrackedAmbulance[];
  selectedAmbulanceId?: string;
  onSelectEmergency?: (incidentId: string) => void;
  hospitals?: HospitalMarkerData[];
  policeUnits?: PoliceUnit[];
  signals?: TrafficSignal[];
  incidentMarkers?: MapIncidentMarker[];
  showTraffic?: boolean;
  showRoutes?: boolean;
  showPolice?: boolean;
  showIncidents?: boolean;
  showSignals?: boolean;
  mapType?: "dark" | "roadmap" | "satellite" | "hybrid";
  onMapReady?: (map: google.maps.Map) => void;
  onError?: (error: Error) => void;
}

const SERTOS_DARK_STYLE: google.maps.MapTypeStyle[] = [
  { elementType: "geometry", stylers: [{ color: "#061326" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#061326" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#94a3b8" }] },
  {
    featureType: "administrative.locality",
    elementType: "labels.text.fill",
    stylers: [{ color: "#f1f5f9" }],
  },
  {
    featureType: "poi",
    elementType: "labels.text.fill",
    stylers: [{ color: "#64748b" }],
  },
  {
    featureType: "poi.park",
    elementType: "geometry",
    stylers: [{ color: "#0a223a" }],
  },
  {
    featureType: "road",
    elementType: "geometry",
    stylers: [{ color: "#132b49" }],
  },
  {
    featureType: "road",
    elementType: "geometry.stroke",
    stylers: [{ color: "#0d1f35" }],
  },
  {
    featureType: "road",
    elementType: "labels.text.fill",
    stylers: [{ color: "#94a3b8" }],
  },
  {
    featureType: "road.highway",
    elementType: "geometry",
    stylers: [{ color: "#1d3d66" }],
  },
  {
    featureType: "road.highway",
    elementType: "geometry.stroke",
    stylers: [{ color: "#102644" }],
  },
  {
    featureType: "transit",
    elementType: "geometry",
    stylers: [{ color: "#112642" }],
  },
  {
    featureType: "water",
    elementType: "geometry",
    stylers: [{ color: "#040d1a" }],
  },
  {
    featureType: "water",
    elementType: "labels.text.fill",
    stylers: [{ color: "#38bdf8" }],
  },
];

export function GoogleMapView({
  center = BENGALURU_CENTER,
  zoom = 14,
  realLocation,
  realAccuracyMeters,
  isRealLocationActive = false,
  followRealLocation = false,
  ambulances,
  selectedAmbulanceId,
  onSelectEmergency,
  hospitals = [],
  policeUnits = [],
  signals = [],
  incidentMarkers = [],
  showTraffic = true,
  showRoutes = true,
  showPolice = true,
  showIncidents = true,
  showSignals = true,
  mapType = "dark",
  onMapReady,
  onError,
}: GoogleMapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const trafficLayerRef = useRef<google.maps.TrafficLayer | null>(null);

  // Overlays
  const ambulanceMarkersRef = useRef<Map<string, google.maps.Marker>>(new Map());
  const routePolylinesRef = useRef<Map<string, google.maps.Polyline>>(new Map());
  const hospitalMarkersRef = useRef<google.maps.Marker[]>([]);
  const policeMarkersRef = useRef<google.maps.Marker[]>([]);
  const signalMarkersRef = useRef<google.maps.Marker[]>([]);
  const incidentMarkersListRef = useRef<google.maps.Marker[]>([]);

  // User location tracking overlay
  const userMarkerRef = useRef<google.maps.Marker | null>(null);
  const userAccuracyCircleRef = useRef<google.maps.Circle | null>(null);

  const [isLoaded, setIsLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Initialize Map
  useEffect(() => {
    let cancelled = false;
    const apiKey = getGoogleMapsApiKey();

    if (!apiKey) {
      setLoadError("Google Maps API key is missing. Please set VITE_GOOGLE_MAPS_API_KEY in frontend/.env.local");
      return;
    }

    const init = async () => {
      try {
        const mapsLib = (await importLibrary("maps")) as google.maps.MapsLibrary;
        if (cancelled || !containerRef.current) return;

        const mapInstance = new mapsLib.Map(containerRef.current, {
          center: { lat: center.lat, lng: center.lng },
          zoom,
          mapTypeId: mapType === "satellite" || mapType === "hybrid" ? mapType : "roadmap",
          styles: mapType === "dark" ? SERTOS_DARK_STYLE : undefined,
          disableDefaultUI: true,
          zoomControl: false,
          gestureHandling: "greedy",
          clickableIcons: false,
        });

        const traffic = new google.maps.TrafficLayer();
        trafficLayerRef.current = traffic;
        if (showTraffic) {
          traffic.setMap(mapInstance);
        }

        mapRef.current = mapInstance;
        setIsLoaded(true);
        setLoadError(null);
        onMapReady?.(mapInstance);
      } catch (err) {
        if (!cancelled) {
          const e = err instanceof Error ? err : new Error(String(err));
          setLoadError(e.message);
          onError?.(e);
        }
      }
    };

    void init();

    return () => {
      cancelled = true;
      trafficLayerRef.current?.setMap(null);
      mapRef.current = null;
    };
  }, []);

  // Sync Map Type & Dark Style
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoaded) return;

    if (mapType === "dark") {
      map.setMapTypeId("roadmap");
      map.setOptions({ styles: SERTOS_DARK_STYLE });
    } else if (mapType === "satellite" || mapType === "hybrid") {
      map.setMapTypeId(mapType);
      map.setOptions({ styles: [] });
    } else {
      map.setMapTypeId("roadmap");
      map.setOptions({ styles: [] });
    }
  }, [mapType, isLoaded]);

  // Sync Google Traffic Layer
  useEffect(() => {
    const map = mapRef.current;
    const traffic = trafficLayerRef.current;
    if (!map || !traffic) return;

    if (showTraffic) {
      traffic.setMap(map);
    } else {
      traffic.setMap(null);
    }
  }, [showTraffic]);

  // Center / Pan Handling
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoaded) return;

    if (followRealLocation && realLocation && isRealLocationActive) {
      map.panTo({ lat: realLocation.lat, lng: realLocation.lng });
    }
  }, [followRealLocation, realLocation, isRealLocationActive, isLoaded]);

  // Render Real User Location Marker & Accuracy Circle
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoaded) return;

    if (!isRealLocationActive || !realLocation) {
      userMarkerRef.current?.setMap(null);
      userMarkerRef.current = null;
      userAccuracyCircleRef.current?.setMap(null);
      userAccuracyCircleRef.current = null;
      return;
    }

    const pos = { lat: realLocation.lat, lng: realLocation.lng };

    // Accuracy Circle
    const accuracy = realAccuracyMeters ?? 15;
    if (!userAccuracyCircleRef.current) {
      userAccuracyCircleRef.current = new google.maps.Circle({
        map,
        center: pos,
        radius: accuracy,
        fillColor: "#24A8FF",
        fillOpacity: 0.18,
        strokeColor: "#24A8FF",
        strokeOpacity: 0.65,
        strokeWeight: 1.5,
        zIndex: 50,
      });
    } else {
      userAccuracyCircleRef.current.setCenter(pos);
      userAccuracyCircleRef.current.setRadius(accuracy);
      userAccuracyCircleRef.current.setMap(map);
    }

    // User Location Dot Marker
    if (!userMarkerRef.current) {
      userMarkerRef.current = new google.maps.Marker({
        map,
        position: pos,
        title: "Your Real Location",
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 9,
          fillColor: "#24A8FF",
          fillOpacity: 1,
          strokeColor: "#FFFFFF",
          strokeWeight: 3,
        },
        zIndex: 100,
      });
    } else {
      userMarkerRef.current.setPosition(pos);
      userMarkerRef.current.setMap(map);
    }
  }, [isRealLocationActive, realLocation, realAccuracyMeters, isLoaded]);

  // Render Ambulances & Routes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoaded) return;

    const currentMarkers = ambulanceMarkersRef.current;
    const currentPolylines = routePolylinesRef.current;
    const seenIds = new Set<string>();

    ambulances.forEach((amb) => {
      seenIds.add(amb.id);
      const isSelected = amb.ambulanceId === selectedAmbulanceId;
      const pos = { lat: amb.position.lat, lng: amb.position.lng };

      let marker = currentMarkers.get(amb.id);
      if (!marker) {
        marker = new google.maps.Marker({
          map,
          position: pos,
          title: `Ambulance ${amb.ambulanceId} - ${amb.emergencyType}`,
          label: {
            text: amb.ambulanceId.replace("SRT-", ""),
            color: "#FFFFFF",
            fontSize: "10px",
            fontWeight: "bold",
          },
          icon: {
            path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
            scale: isSelected ? 7 : 5.5,
            fillColor: isSelected ? "#24A8FF" : "#00D084",
            fillOpacity: 1,
            strokeColor: "#0A1729",
            strokeWeight: 2,
          },
          zIndex: isSelected ? 90 : 80,
        });

        marker.addListener("click", () => {
          onSelectEmergency?.(amb.incidentId);
        });

        currentMarkers.set(amb.id, marker);
      } else {
        marker.setPosition(pos);
        marker.setZIndex(isSelected ? 90 : 80);
        marker.setIcon({
          path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
          scale: isSelected ? 7 : 5.5,
          fillColor: isSelected ? "#24A8FF" : "#00D084",
          fillOpacity: 1,
          strokeColor: "#0A1729",
          strokeWeight: 2,
        });
      }

      // Route Polyline
      if (showRoutes && amb.routeWaypoints.length > 0) {
        let poly = currentPolylines.get(amb.id);
        const path = amb.routeWaypoints.map((w) => ({ lat: w.lat, lng: w.lng }));

        if (!poly) {
          poly = new google.maps.Polyline({
            map,
            path,
            strokeColor: isSelected ? "#24A8FF" : "#38BDF8",
            strokeOpacity: isSelected ? 0.95 : 0.45,
            strokeWeight: isSelected ? 6 : 3.5,
            zIndex: isSelected ? 40 : 30,
          });
          currentPolylines.set(amb.id, poly);
        } else {
          poly.setPath(path);
          poly.setOptions({
            strokeColor: isSelected ? "#24A8FF" : "#38BDF8",
            strokeOpacity: isSelected ? 0.95 : 0.45,
            strokeWeight: isSelected ? 6 : 3.5,
            zIndex: isSelected ? 40 : 30,
          });
          poly.setMap(map);
        }
      } else {
        currentPolylines.get(amb.id)?.setMap(null);
      }
    });

    // Cleanup removed ambulances
    currentMarkers.forEach((marker, id) => {
      if (!seenIds.has(id)) {
        marker.setMap(null);
        currentMarkers.delete(id);
      }
    });
    currentPolylines.forEach((poly, id) => {
      if (!seenIds.has(id) || !showRoutes) {
        poly.setMap(null);
        currentPolylines.delete(id);
      }
    });
  }, [ambulances, selectedAmbulanceId, showRoutes, isLoaded, onSelectEmergency]);

  // Render Hospitals
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoaded) return;

    hospitalMarkersRef.current.forEach((m) => m.setMap(null));
    hospitalMarkersRef.current = [];

    hospitals.forEach((hosp) => {
      const marker = new google.maps.Marker({
        map,
        position: { lat: hosp.position.lat, lng: hosp.position.lng },
        title: `${hosp.name} (${hosp.availableBeds ?? "--"} beds available)`,
        label: {
          text: "H",
          color: "#FFFFFF",
          fontSize: "12px",
          fontWeight: "bold",
        },
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 14,
          fillColor: "#EF4444",
          fillOpacity: 0.95,
          strokeColor: "#FFFFFF",
          strokeWeight: 2,
        },
        zIndex: 70,
      });
      hospitalMarkersRef.current.push(marker);
    });
  }, [hospitals, isLoaded]);

  // Render Police Units
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoaded) return;

    policeMarkersRef.current.forEach((m) => m.setMap(null));
    policeMarkersRef.current = [];

    if (!showPolice) return;

    policeUnits.forEach((unit) => {
      const marker = new google.maps.Marker({
        map,
        position: { lat: unit.position.lat, lng: unit.position.lng },
        title: `${unit.callSign} - ${unit.officerName} (${unit.status})`,
        label: {
          text: "P",
          color: "#24A8FF",
          fontSize: "11px",
          fontWeight: "bold",
        },
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 11,
          fillColor: "#0A1729",
          fillOpacity: 1,
          strokeColor: "#24A8FF",
          strokeWeight: 2,
        },
        zIndex: 60,
      });
      policeMarkersRef.current.push(marker);
    });
  }, [policeUnits, showPolice, isLoaded]);

  // Render Traffic Signals
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoaded) return;

    signalMarkersRef.current.forEach((m) => m.setMap(null));
    signalMarkersRef.current = [];

    if (!showSignals) return;

    signals.forEach((sig) => {
      const lightColor =
        sig.currentLight === "GREEN"
          ? "#00D084"
          : sig.currentLight === "YELLOW"
            ? "#F59E0B"
            : "#EF4444";

      const marker = new google.maps.Marker({
        map,
        position: { lat: sig.position.lat, lng: sig.position.lng },
        title: `${sig.location} [${sig.currentLight}] - ${sig.countdownSeconds}s`,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 6,
          fillColor: lightColor,
          fillOpacity: 1,
          strokeColor: "#0A1729",
          strokeWeight: 1.5,
        },
        zIndex: 55,
      });
      signalMarkersRef.current.push(marker);
    });
  }, [signals, showSignals, isLoaded]);

  // Render Incidents
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isLoaded) return;

    incidentMarkersListRef.current.forEach((m) => m.setMap(null));
    incidentMarkersListRef.current = [];

    if (!showIncidents) return;

    incidentMarkers.forEach((inc) => {
      const marker = new google.maps.Marker({
        map,
        position: { lat: inc.position.lat, lng: inc.position.lng },
        title: `${inc.title} - ${inc.severity}`,
        label: {
          text: "!",
          color: "#FBBF24",
          fontSize: "12px",
          fontWeight: "900",
        },
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 10,
          fillColor: "#451A03",
          fillOpacity: 0.95,
          strokeColor: "#F59E0B",
          strokeWeight: 2,
        },
        zIndex: 65,
      });
      incidentMarkersListRef.current.push(marker);
    });
  }, [incidentMarkers, showIncidents, isLoaded]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />

      {loadError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#061326]/90 p-4 text-center">
          <p className="text-sm font-semibold text-[#EF4444]">{loadError}</p>
          <p className="mt-1 text-xs text-[#94A3B8]">
            Configure your Google Maps API key or toggle to the Dark Vector Map.
          </p>
        </div>
      )}
    </div>
  );
}
