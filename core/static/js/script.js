let map = null;
let routeLayers = [];
let markers = [];
let currentRouteIndex = -1;
let routesData = [];
let geocodedPoints = {};
function initMap() {
    DG.then(function() {
        DG.key = '5ef601a4-d465-4d49-8a46-e8f62b1c159a';
        const ekbCenter = [56.838011, 60.597465];
        map = DG.map('map', {
            center: ekbCenter,
            zoom: 13,
            zoomControl: true,
            geoclicker: true
        });
        DG.control.scale({imperial: false}).addTo(map);
        if (geocodedPoints.start && geocodedPoints.end && routesData.length === 0) {
            showPointsOnMap();
        }
        if (routesData.length > 0) {
            setTimeout(() => {
                showRouteOnMap(0);
                const firstAccordion = document.getElementById('heading1');
                if (firstAccordion) {
                    const button = firstAccordion.querySelector('.accordion-button');
                    if (button && button.classList.contains('collapsed')) {
                        button.click();
                    }
                }
            }, 500);
        }
    });
}
function showPointsOnMap() {
    clearMap();
    
    if (geocodedPoints.start) {
        const startMarker = DG.marker(
            [geocodedPoints.start.lat, geocodedPoints.start.lon],
            {
                icon: DG.divIcon({
                    className: 'route-marker-start',
                    html: '<div style="background-color:#28a745; width:24px; height:24px; border-radius:50%; border:3px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3); display:flex; align-items:center; justify-content:center;"><i class="fas fa-play" style="color:white; font-size:12px;"></i></div>',
                    iconSize: [30, 30],
                    iconAnchor: [15, 15]
                })
            }
        ).addTo(map);
        
        startMarker.bindPopup(`
            <div class="route-info-window">
                <strong>📍 Начало маршрута</strong><br>
                ${geocodedPoints.start.address || 'Не указано'}<br>
                <small class="text-muted">
                    Координаты: ${geocodedPoints.start.lat?.toFixed(6) || 'N/A'}, 
                    ${geocodedPoints.start.lon?.toFixed(6) || 'N/A'}
                </small>
            </div>
        `);
        markers.push(startMarker);
    }
    
    if (geocodedPoints.end) {
        const endMarker = DG.marker(
            [geocodedPoints.end.lat, geocodedPoints.end.lon],
            {
                icon: DG.divIcon({
                    className: 'route-marker-end',
                    html: '<div style="background-color:#dc3545; width:24px; height:24px; border-radius:50%; border:3px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3); display:flex; align-items:center; justify-content:center;"><i class="fas fa-flag" style="color:white; font-size:12px;"></i></div>',
                    iconSize: [30, 30],
                    iconAnchor: [15, 15]
                })
            }
        ).addTo(map);
        
        endMarker.bindPopup(`
            <div class="route-info-window">
                <strong>🏁 Конец маршрута</strong><br>
                ${geocodedPoints.end.address || 'Не указано'}<br>
                <small class="text-muted">
                    Координаты: ${geocodedPoints.end.lat?.toFixed(6) || 'N/A'}, 
                    ${geocodedPoints.end.lon?.toFixed(6) || 'N/A'}
                </small>
            </div>
        `);
        markers.push(endMarker);
    }
    
    if (geocodedPoints.start && geocodedPoints.end) {
        const bounds = DG.latLngBounds([
            [geocodedPoints.start.lat, geocodedPoints.start.lon],
            [geocodedPoints.end.lat, geocodedPoints.end.lon]
        ]);
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}
function showRouteOnMap(routeIndex) {
    if (routeIndex === currentRouteIndex) {
        return;
    }
    
    currentRouteIndex = routeIndex;
    clearMap();
    
    if (routesData.length > 0 && routeIndex < routesData.length) {
        const route = routesData[routeIndex];
        if (geocodedPoints.start && geocodedPoints.end) {
            const startMarker = DG.marker(
                [geocodedPoints.start.lat, geocodedPoints.start.lon],
                {
                    icon: DG.divIcon({
                        className: 'route-marker-start',
                        html: '<div style="background-color:#28a745; width:24px; height:24px; border-radius:50%; border:3px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3); display:flex; align-items:center; justify-content:center;"><i class="fas fa-play" style="color:white; font-size:12px;"></i></div>',
                        iconSize: [30, 30],
                        iconAnchor: [15, 15]
                    })
                }
            ).addTo(map);
            
            startMarker.bindPopup(`
                <div class="route-info-window">
                    <strong>📍 Начало маршрута</strong><br>
                    ${geocodedPoints.start.address || 'Не указано'}<br>
                    <small class="text-muted">Маршрут ${routeIndex + 1}</small>
                </div>
            `);
            markers.push(startMarker);
            
            const endMarker = DG.marker(
                [geocodedPoints.end.lat, geocodedPoints.end.lon],
                {
                    icon: DG.divIcon({
                        className: 'route-marker-end',
                        html: '<div style="background-color:#dc3545; width:24px; height:24px; border-radius:50%; border:3px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3); display:flex; align-items:center; justify-content:center;"><i class="fas fa-flag" style="color:white; font-size:12px;"></i></div>',
                        iconSize: [30, 30],
                        iconAnchor: [15, 15]
                    })
                }
            ).addTo(map);
            
            endMarker.bindPopup(`
                <div class="route-info-window">
                    <strong>🏁 Конец маршрута</strong><br>
                    ${geocodedPoints.end.address || 'Не указано'}<br>
                    <small class="text-muted">Маршрут ${routeIndex + 1}</small>
                </div>
            `);
            markers.push(endMarker);
        }
        
        const routeCoordinates = route.coordinates || [];
        
        if (routeCoordinates.length > 0 && routeCoordinates[0].length > 0) {
            let lineColor = '#007bff';
            let dashArray = null;
            
            if (route.travel_mode === 'car') {
                lineColor = '#ff3333';
            } else if (route.travel_mode === 'bicycle') {
                lineColor = '#17a2b8';
            } else if (route.travel_mode === 'pedestrian') {
                lineColor = '#28a745';
                dashArray = '10, 10';
            }
            
            // Создаем полилинию для всего маршрута
            const polyline = DG.polyline(routeCoordinates[0], {
                color: lineColor,
                weight: 5,
                opacity: 0.8,
                lineJoin: 'round',
                lineCap: 'round',
                dashArray: dashArray
            }).addTo(map);
            polyline.bindPopup(`
                <div class="route-info-window">
                    <strong>${route.mode_display || 'Маршрут'}</strong><br>
                    <small>Время: ${route.total_time} мин</small><br>
                    <small>Расстояние: ${route.total_distance ? Math.round(route.total_distance) + ' м' : 'N/A'}</small>
                </div>
            `);
            
            routeLayers.push(polyline);
            if (route.segments) {
                let addedStops = new Set();
                
                route.segments.forEach((segment, segmentIndex) => {
                    if (segment.type === 'transport' && segment.details.from_stop) {
                        let stopCoords = null;
                        
                        if (segment.details.from_stop_coords) {
                            stopCoords = segment.details.from_stop_coords;
                        } else if (routeCoordinates[0] && routeCoordinates[0].length > 0) {
                            const totalSegments = route.segments.filter(s => s.type === 'transport').length;
                            const segmentRatio = segmentIndex / Math.max(totalSegments, 1);
                            const stopIndex = Math.floor(routeCoordinates[0].length * segmentRatio);
                            stopCoords = routeCoordinates[0][Math.min(stopIndex, routeCoordinates[0].length - 1)];
                        }
                        
                        if (stopCoords && geocodedPoints.start) {
                            const startLat = geocodedPoints.start.lat;
                            const startLon = geocodedPoints.start.lon;
                            const stopLat = stopCoords[0];
                            const stopLon = stopCoords[1];
                            
                            const latDiff = Math.abs(startLat - stopLat);
                            const lonDiff = Math.abs(startLon - stopLon);
                            const distance = Math.sqrt(latDiff * latDiff + lonDiff * lonDiff);
                            
                            if (distance < 0.001 && segmentIndex === 0) {
                                stopCoords = [
                                    stopLat + 0.001,
                                    stopLon + 0.001
                                ];
                            }
                        }
                        
                        if (stopCoords) {
                            const stopKey = `${stopCoords[0].toFixed(6)}_${stopCoords[1].toFixed(6)}`;
                            
                            if (!addedStops.has(stopKey)) {
                                const stopMarker = DG.marker(stopCoords, {
                                    icon: DG.divIcon({
                                        className: 'stop-marker',
                                        html: `<div style="background-color:#ffc107; width:24px; height:24px; border-radius:50%; border:3px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3); display:flex; align-items:center; justify-content:center; font-weight:bold; color:#333; font-size:12px;">${segmentIndex + 1}</div>`,
                                        iconSize: [30, 30],
                                        iconAnchor: [15, 15]
                                    })
                                }).addTo(map);
                                
                                stopMarker.bindPopup(`
                                    <div class="stop-info-window">
                                        <strong>🚏 ${segment.details.from_stop}</strong><br>
                                        <small>${segment.details.transport_name || 'Транспорт'}</small><br>
                                        <small>Маршрут: ${segment.details.route_display || 'Не указан'}</small>
                                        ${segment.details.stops_count ? `<br><small>${segment.details.stops_count} остановок</small>` : ''}
                                    </div>
                                `);
                                markers.push(stopMarker);
                                addedStops.add(stopKey);
                            }
                        }
                    }
                    
                    if (segmentIndex === route.segments.length - 1 && segment.type === 'transport' && segment.details.to_stop) {
                        let stopCoords = null;
                        
                        if (segment.details.to_stop_coords) {
                            stopCoords = segment.details.to_stop_coords;
                        } else if (geocodedPoints.end) {
                            stopCoords = [geocodedPoints.end.lat, geocodedPoints.end.lon];
                        }
                        
                        if (stopCoords) {
                            const stopKey = `${stopCoords[0].toFixed(6)}_${stopCoords[1].toFixed(6)}`;
                            
                            if (!addedStops.has(stopKey)) {
                                const stopMarker = DG.marker(stopCoords, {
                                    icon: DG.divIcon({
                                        className: 'stop-marker-end',
                                        html: '<div style="background-color:#28a745; width:24px; height:24px; border-radius:50%; border:3px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3); display:flex; align-items:center; justify-content:center; font-weight:bold; color:white; font-size:12px;">🏁</div>',
                                        iconSize: [30, 30],
                                        iconAnchor: [15, 15]
                                    })
                                }).addTo(map);
                                
                                stopMarker.bindPopup(`
                                    <div class="stop-info-window">
                                        <strong>🏁 ${segment.details.to_stop}</strong><br>
                                        <small>Конечная остановка</small>
                                    </div>
                                `);
                                markers.push(stopMarker);
                                addedStops.add(stopKey);
                            }
                        }
                    }
                });
            }
            const bounds = DG.latLngBounds(routeCoordinates[0]);
            map.fitBounds(bounds, { padding: [50, 50] });
        } else {
            if (geocodedPoints.start && geocodedPoints.end) {
                const bounds = DG.latLngBounds([
                    [geocodedPoints.start.lat, geocodedPoints.start.lon],
                    [geocodedPoints.end.lat, geocodedPoints.end.lon]
                ]);
                map.fitBounds(bounds, { padding: [50, 50] });
            }
        }
        document.querySelectorAll('.accordion-button').forEach((btn, index) => {
            if (index === routeIndex) {
                btn.classList.add('active-route');
                btn.style.backgroundColor = '#e7f1ff';
            } else {
                btn.classList.remove('active-route');
                btn.style.backgroundColor = '';
            }
        });
    }
}
function clearMap() {
    routeLayers.forEach(layer => {
        if (map.hasLayer(layer)) {
            map.removeLayer(layer);
        }
    });
    markers.forEach(marker => {
        if (map.hasLayer(marker)) {
            map.removeLayer(marker);
        }
    });
    routeLayers = [];
    markers = [];
}

function resetMapView() {
    if (routesData.length > 0 && currentRouteIndex >= 0) {
        showRouteOnMap(currentRouteIndex);
    } else if (geocodedPoints.start && geocodedPoints.end) {
        showPointsOnMap();
    } else {
        map.setView([56.838011, 60.597465], 13);
    }
}
function toggleFullscreen() {
    const mapContainer = document.getElementById('map');
    if (!document.fullscreenElement) {
        if (mapContainer.requestFullscreen) {
            mapContainer.requestFullscreen();
        } else if (mapContainer.webkitRequestFullscreen) {
            mapContainer.webkitRequestFullscreen();
        } else if (mapContainer.msRequestFullscreen) {
            mapContainer.msRequestFullscreen();
        }
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        }
    }
}

// Автодополнение адресов
function setupAutocomplete(inputId, itemsContainerId) {
    const input = document.getElementById(inputId);
    const itemsContainer = document.getElementById(itemsContainerId);
    
    if (!input || !itemsContainer) return;
    
    let currentFocus = -1;
    let timeoutId = null;
    
    input.addEventListener('input', function(e) {
        const query = this.value.trim();
        itemsContainer.innerHTML = '';
        currentFocus = -1;
        
        if (query.length < 2) {
            return;
        }
        
        if (timeoutId) {
            clearTimeout(timeoutId);
        }
        
        timeoutId = setTimeout(() => {
            fetchAutocompleteResults(query, itemsContainer, input);
        }, 300);
    });
    
    input.addEventListener('keydown', function(e) {
        const items = itemsContainer.getElementsByClassName('autocomplete-item');
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            currentFocus = Math.min(currentFocus + 1, items.length - 1);
            setActiveItem(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            currentFocus = Math.max(currentFocus - 1, -1);
            setActiveItem(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (currentFocus > -1 && items[currentFocus]) {
                items[currentFocus].click();
            }
        } else if (e.key === 'Escape') {
            itemsContainer.innerHTML = '';
        }
    });
    
    document.addEventListener('click', function(e) {
        if (!itemsContainer.contains(e.target) && e.target !== input) {
            itemsContainer.innerHTML = '';
        }
    });
}

// Запрос результатов автодополнения
function fetchAutocompleteResults(query, container, input) {
    fetch(`/api/autocomplete/?q=${encodeURIComponent(query)}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Ошибка сети');
            }
            return response.json();
        })
        .then(data => {
            container.innerHTML = '';
            
            if (data.results && data.results.length > 0) {
                data.results.forEach((item, index) => {
                    const itemElement = document.createElement('div');
                    itemElement.className = 'autocomplete-item';
                    itemElement.innerHTML = `
                        <div class="fw-semibold">${item.label}</div>
                        <small class="text-muted">${item.full_address || ''}</small>
                    `;
                    
                    itemElement.addEventListener('click', function() {
                        input.value = item.label;
                        container.innerHTML = '';
                        
                        input.dataset.lat = item.lat;
                        input.dataset.lon = item.lon;
                    });
                    
                    itemElement.addEventListener('mouseenter', function() {
                        removeActiveItems(container);
                        this.classList.add('active');
                    });
                    
                    container.appendChild(itemElement);
                });
            } else {
                const noResults = document.createElement('div');
                noResults.className = 'autocomplete-item text-muted';
                noResults.textContent = 'Ничего не найдено';
                container.appendChild(noResults);
            }
        })
        .catch(error => {
            console.error('Ошибка автодополнения:', error);
            const errorElement = document.createElement('div');
                errorElement.className = 'autocomplete-item text-danger';
                errorElement.textContent = 'Ошибка загрузки данных';
                container.appendChild(errorElement);
            });
    }
    function setActiveItem(items) {
        removeActiveItems();
        if (currentFocus >= 0 && items[currentFocus]) {
            items[currentFocus].classList.add('active');
            items[currentFocus].scrollIntoView({ block: 'nearest' });
        }
    }
    function removeActiveItems() {
        document.querySelectorAll('.autocomplete-item.active').forEach(item => {
            item.classList.remove('active');
        });
    }
    function setTravelMode(mode) {
        document.getElementById('id_travel_mode').value = mode;
        
        document.querySelectorAll('.switch-btn').forEach(btn => {
            if (btn.dataset.mode === mode) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        const filtersPanel = document.getElementById('transport-filters');
        if (mode === 'public') {
            filtersPanel.style.display = 'block';
        } else {
            filtersPanel.style.display = 'none';
        }
    }
    function updateTransportFilters() {
        const allCheckbox = document.getElementById('transport_all');
        const specificCheckboxes = document.querySelectorAll('input[name="transport_types"]:not([value="all"])');
        const checkedSpecific = Array.from(specificCheckboxes).filter(cb => cb.checked);
        
        if (checkedSpecific.length > 0) {
            allCheckbox.checked = false;
        }
    }
    function toggleAllTransportTypes(checkbox) {
        const specificCheckboxes = document.querySelectorAll('input[name="transport_types"]:not([value="all"])');
        
        if (checkbox.checked) {
            specificCheckboxes.forEach(cb => {
                cb.checked = false;
            });
        }
    }

    // Показ загрузки
    function showLoading() {
        document.getElementById('loadingOverlay').style.display = 'flex';
    }

    // Скрытие загрузки
    function hideLoading() {
        document.getElementById('loadingOverlay').style.display = 'none';
    }
    function initializeDjangoData() {
        if (typeof window.djangoData !== 'undefined') {
            routesData = window.djangoData.routesData || [];
            geocodedPoints = window.djangoData.geocodedPoints || {};
        }
    }
    document.addEventListener('DOMContentLoaded', function() {
        initializeDjangoData();
        initMap();
        setupAutocomplete('id_start_point', 'start-autocomplete');
        setupAutocomplete('id_end_point', 'end-autocomplete');
        const form = document.getElementById('route-form');
        if (form) {
            form.addEventListener('submit', function(e) {
                const startInput = document.getElementById('id_start_point');
                const endInput = document.getElementById('id_end_point');
                
                if (!startInput.value.trim() || !endInput.value.trim()) {
                    e.preventDefault();
                    alert('Пожалуйста, заполните оба поля: "Откуда" и "Куда"');
                    return;
                }
                
                showLoading();
                
                setTimeout(hideLoading, 10000);
            });
        }
        document.querySelectorAll('.accordion-button').forEach((button, index) => {
            button.addEventListener('click', function() {
                setTimeout(() => {
                    showRouteOnMap(index);
                }, 100);
            });
        });
        if (document.querySelector('.error-box')) {
            setTimeout(() => {
                document.querySelector('.error-box').style.opacity = '0.7';
            }, 5000);
        }
    });
    document.addEventListener('DOMContentLoaded', function() {
        const travelModeSelect = document.getElementById('travel-mode');
        const transportTypesSelect = document.getElementById('transport-types');
        const maxTransfersSelect = document.getElementById('max-transfers');
        const onlyDirectCheckbox = document.getElementById('only-direct');
        
        function toggleTransportFilters() {
            const selectedMode = travelModeSelect.value;
            
            if (selectedMode !== 'public') {
                Array.from(transportTypesSelect.options).forEach(option => {
                    option.selected = false;
                });
                maxTransfersSelect.value = 'any';
                onlyDirectCheckbox.checked = false;
                const filtersBlock = document.querySelector('.transport-filters');
                if (filtersBlock) {
                    filtersBlock.style.display = 'none';
                }
            } else {
                const filtersBlock = document.querySelector('.transport-filters');
                if (filtersBlock) {
                    filtersBlock.style.display = 'block';
                }
            }
        }
        travelModeSelect.addEventListener('change', toggleTransportFilters);
        toggleTransportFilters();
    });
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('msfullscreenchange', handleFullscreenChange);
    
    function handleFullscreenChange() {
        if (!document.fullscreenElement && !document.webkitFullscreenElement && !document.msFullscreenElement) {
            setTimeout(resetMapView, 100);
        }
    }