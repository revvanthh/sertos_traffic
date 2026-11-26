import { useCallback, useEffect, useRef, useState } from "react";
import type { LatLng } from "../types/police";

export interface RealLocationState {
  position: LatLng | null;
  accuracyMeters: number | null;
  heading: number | null;
  speedKmh: number | null;
  altitudeMeters: number | null;
  timestamp: Date | null;
  isTracking: boolean;
  status: "idle" | "requesting" | "tracking" | "denied" | "unavailable" | "timeout" | "error";
  errorMessage: string | null;
}

export function useRealLocation(autoStart = false) {
  const [state, setState] = useState<RealLocationState>({
    position: null,
    accuracyMeters: null,
    heading: null,
    speedKmh: null,
    altitudeMeters: null,
    timestamp: null,
    isTracking: false,
    status: "idle",
    errorMessage: null,
  });

  const watchIdRef = useRef<number | null>(null);

  const stopTracking = useCallback(() => {
    if (watchIdRef.current !== null && navigator.geolocation) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    setState((prev) => ({
      ...prev,
      isTracking: false,
      status: "idle",
    }));
  }, []);

  const startTracking = useCallback(() => {
    if (!navigator.geolocation) {
      setState((prev) => ({
        ...prev,
        isTracking: false,
        status: "unavailable",
        errorMessage: "Geolocation is not supported by your browser.",
      }));
      return;
    }

    if (watchIdRef.current !== null) {
      // Already running
      return;
    }

    setState((prev) => ({
      ...prev,
      isTracking: true,
      status: "requesting",
      errorMessage: null,
    }));

    try {
      const id = navigator.geolocation.watchPosition(
        (pos) => {
          const lat = pos.coords.latitude;
          const lng = pos.coords.longitude;
          const accuracy = pos.coords.accuracy;
          const heading = pos.coords.heading;
          const speedMs = pos.coords.speed;
          const speedKmh = speedMs !== null && speedMs >= 0 ? Math.round(speedMs * 3.6) : null;
          const altitude = pos.coords.altitude;

          setState({
            position: { lat, lng },
            accuracyMeters: accuracy ? Math.round(accuracy) : null,
            heading: heading ?? null,
            speedKmh,
            altitudeMeters: altitude ? Math.round(altitude) : null,
            timestamp: new Date(pos.timestamp),
            isTracking: true,
            status: "tracking",
            errorMessage: null,
          });
        },
        (err) => {
          let status: RealLocationState["status"] = "error";
          let message = "Unable to retrieve location.";

          if (err.code === 1) {
            status = "denied";
            message = "Location permission was denied. Please allow location access in your browser.";
          } else if (err.code === 2) {
            status = "unavailable";
            message = "Location position is unavailable. Please check your device GPS / network.";
          } else if (err.code === 3) {
            status = "timeout";
            message = "Location request timed out. Retrying GPS lock...";
          }

          setState((prev) => ({
            ...prev,
            status,
            errorMessage: message,
          }));
        },
        {
          enableHighAccuracy: true,
          maximumAge: 2000,
          timeout: 15000,
        },
      );

      watchIdRef.current = id;
    } catch (e) {
      setState((prev) => ({
        ...prev,
        isTracking: false,
        status: "error",
        errorMessage: e instanceof Error ? e.message : "Failed to initiate location tracker.",
      }));
    }
  }, []);

  const toggleTracking = useCallback(() => {
    if (state.isTracking) {
      stopTracking();
    } else {
      startTracking();
    }
  }, [state.isTracking, startTracking, stopTracking]);

  useEffect(() => {
    let timer: number | undefined;
    if (autoStart) {
      timer = window.setTimeout(() => {
        startTracking();
      }, 0);
    }
    return () => {
      if (timer) window.clearTimeout(timer);
      if (watchIdRef.current !== null && navigator.geolocation) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
    };
  }, [autoStart, startTracking]);

  return {
    ...state,
    startTracking,
    stopTracking,
    toggleTracking,
  };
}
