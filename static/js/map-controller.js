/**
 * Map Controller for Real-time Vehicle Tracking
 * Manages Leaflet map with dynamic vehicle markers
 * 
 * Features:
 * - Vehicle markers with custom icons
 * - Popup with vehicle details
 * - Automatic marker updates
 * - Direction-based coloring
 * - Smooth marker transitions
 * 
 * @author Brandon Trigueros Lara
 * @date January 27, 2026
 */

class MapController {
    constructor(mapElementId, options = {}) {
        this.mapElementId = mapElementId;
        this.map = null;
        this.markers = {}; // vehicleId -> marker
        this.options = {
            center: options.center || [42.3601, -71.0589], // Boston default
            zoom: options.zoom || 13,
            minZoom: options.minZoom || 10,
            maxZoom: options.maxZoom || 18,
            ...options
        };
        
        // Icons for different directions
        this.icons = {
            direction0: this._createIcon('#3B82F6'), // Blue
            direction1: this._createIcon('#10B981'), // Green
            unknown: this._createIcon('#6B7280')     // Gray
        };
    }

    /**
     * Initialize map
     */
    initialize() {
        // Create map
        this.map = L.map(this.mapElementId).setView(
            this.options.center,
            this.options.zoom
        );

        // Add tile layer (OpenStreetMap)
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            minZoom: this.options.minZoom,
            maxZoom: this.options.maxZoom
        }).addTo(this.map);

        console.log('[Map] Initialized at', this.options.center);
    }

    /**
     * Create custom icon for vehicle marker
     */
    _createIcon(color) {
        return L.divIcon({
            className: 'vehicle-marker',
            html: `
                <div style="
                    background-color: ${color};
                    width: 24px;
                    height: 24px;
                    border-radius: 50%;
                    border: 3px solid white;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                ">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
                        <path d="M12 2L4 5v6.09c0 5.05 3.41 9.76 8 10.91 4.59-1.15 8-5.86 8-10.91V5l-8-3zm0 16l-4-4 1.41-1.41L12 15.17l6.59-6.59L20 10l-8 8z"/>
                    </svg>
                </div>
            `,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
            popupAnchor: [0, -12]
        });
    }

    /**
     * Update or add vehicle marker
     * @param {Object} vehicle - Vehicle data from WebSocket
     */
    updateVehicle(vehicle) {
        const vehicleId = vehicle.vehicle?.id || vehicle.id;
        if (!vehicleId) {
            console.warn('[Map] Vehicle without ID:', vehicle);
            return;
        }

        const lat = vehicle.position?.latitude;
        const lng = vehicle.position?.longitude;
        
        if (!lat || !lng) {
            console.warn('[Map] Vehicle without position:', vehicle);
            return;
        }

        const position = [lat, lng];

        // Determine icon based on direction
        const direction = vehicle.trip?.direction_id;
        let icon;
        if (direction === 0) {
            icon = this.icons.direction0;
        } else if (direction === 1) {
            icon = this.icons.direction1;
        } else {
            icon = this.icons.unknown;
        }

        // Update existing marker or create new one
        if (this.markers[vehicleId]) {
            // Update existing marker
            const marker = this.markers[vehicleId];
            marker.setLatLng(position);
            marker.setIcon(icon);
            
            // Update popup content
            const popupContent = this._createPopupContent(vehicle);
            marker.getPopup().setContent(popupContent);
            
            console.log(`[Map] Updated vehicle ${vehicleId} at`, position);
        } else {
            // Create new marker
            const marker = L.marker(position, { icon })
                .addTo(this.map)
                .bindPopup(this._createPopupContent(vehicle));
            
            this.markers[vehicleId] = marker;
            console.log(`[Map] Added vehicle ${vehicleId} at`, position);
        }
    }

    /**
     * Update multiple vehicles at once
     * @param {Array} vehicles - Array of vehicle data
     */
    updateVehicles(vehicles) {
        vehicles.forEach(vehicle => this.updateVehicle(vehicle));
        
        // Fit bounds to show all markers
        if (Object.keys(this.markers).length > 0) {
            this.fitBounds();
        }
    }

    /**
     * Remove vehicle marker
     * @param {string} vehicleId - Vehicle ID to remove
     */
    removeVehicle(vehicleId) {
        if (this.markers[vehicleId]) {
            this.map.removeLayer(this.markers[vehicleId]);
            delete this.markers[vehicleId];
            console.log(`[Map] Removed vehicle ${vehicleId}`);
        }
    }

    /**
     * Clear all vehicle markers
     */
    clearVehicles() {
        Object.values(this.markers).forEach(marker => {
            this.map.removeLayer(marker);
        });
        this.markers = {};
        console.log('[Map] Cleared all vehicles');
    }

    /**
     * Fit map bounds to show all markers
     */
    fitBounds() {
        const markerPositions = Object.values(this.markers).map(m => m.getLatLng());
        if (markerPositions.length > 0) {
            const bounds = L.latLngBounds(markerPositions);
            this.map.fitBounds(bounds, { padding: [50, 50] });
        }
    }

    /**
     * Create popup content for vehicle marker
     */
    _createPopupContent(vehicle) {
        const vehicleId = vehicle.vehicle?.id || vehicle.id || 'Unknown';
        const label = vehicle.vehicle?.label || 'N/A';
        const routeId = vehicle.trip?.route_id || 'N/A';
        const tripId = vehicle.trip?.trip_id || 'N/A';
        const direction = vehicle.trip?.direction_id;
        const directionText = direction === 0 ? 'Outbound (0)' : direction === 1 ? 'Inbound (1)' : 'Unknown';
        const speed = vehicle.position?.speed ? `${Math.round(vehicle.position.speed * 3.6)} km/h` : 'N/A';
        const bearing = vehicle.position?.bearing ? `${Math.round(vehicle.position.bearing)}°` : 'N/A';
        const timestamp = vehicle.timestamp ? new Date(vehicle.timestamp * 1000).toLocaleTimeString() : 'N/A';

        return `
            <div class="vehicle-popup">
                <h4 style="margin: 0 0 8px 0; color: #1F2937;">🚌 ${label}</h4>
                <table style="font-size: 12px; width: 100%;">
                    <tr>
                        <td style="padding: 2px 8px 2px 0; color: #6B7280;">Vehicle ID:</td>
                        <td style="padding: 2px 0; font-weight: 600;">${vehicleId}</td>
                    </tr>
                    <tr>
                        <td style="padding: 2px 8px 2px 0; color: #6B7280;">Route:</td>
                        <td style="padding: 2px 0; font-weight: 600;">${routeId}</td>
                    </tr>
                    <tr>
                        <td style="padding: 2px 8px 2px 0; color: #6B7280;">Trip:</td>
                        <td style="padding: 2px 0; font-size: 11px;">${tripId}</td>
                    </tr>
                    <tr>
                        <td style="padding: 2px 8px 2px 0; color: #6B7280;">Direction:</td>
                        <td style="padding: 2px 0;">
                            <span style="
                                background-color: ${direction === 0 ? '#DBEAFE' : direction === 1 ? '#D1FAE5' : '#F3F4F6'};
                                color: ${direction === 0 ? '#1E40AF' : direction === 1 ? '#065F46' : '#374151'};
                                padding: 2px 6px;
                                border-radius: 4px;
                                font-size: 11px;
                                font-weight: 600;
                            ">${directionText}</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 2px 8px 2px 0; color: #6B7280;">Speed:</td>
                        <td style="padding: 2px 0;">${speed}</td>
                    </tr>
                    <tr>
                        <td style="padding: 2px 8px 2px 0; color: #6B7280;">Bearing:</td>
                        <td style="padding: 2px 0;">${bearing}</td>
                    </tr>
                    <tr>
                        <td style="padding: 2px 8px 2px 0; color: #6B7280;">Updated:</td>
                        <td style="padding: 2px 0; font-size: 11px;">${timestamp}</td>
                    </tr>
                </table>
            </div>
        `;
    }

    /**
     * Get vehicle count
     */
    getVehicleCount() {
        return Object.keys(this.markers).length;
    }

    /**
     * Get map instance (for advanced usage)
     */
    getMap() {
        return this.map;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MapController;
}
