/* ZIP search: outline one boundary and display its existing PM assignment. */
function pcgAddZipSearch(map, zipLayer) {
    var selectedLayer = null;
    var layersByZip = Object.create(null);
    zipLayer.eachLayer(function (layer) {
        layersByZip[String(layer.feature.properties['ZIP Code'])] = layer;
    });

    var control = L.control({position: 'topleft'});
    control.onAdd = function () {
        var container = L.DomUtil.create('div', 'pcg-zip-search leaflet-bar');
        container.style.cssText = 'background:white;padding:12px;width:250px;max-width:calc(100vw - 90px);box-sizing:border-box;color:#202020;font:14px/1.4 Arial,sans-serif;';
        var form = L.DomUtil.create('form', '', container);
        form.setAttribute('role', 'search');
        var label = L.DomUtil.create('label', '', form);
        label.textContent = 'Search ZIP Code';
        label.style.cssText = 'display:block;font-weight:700;margin-bottom:6px;';
        var input = L.DomUtil.create('input', '', label);
        input.type = 'search';
        input.inputMode = 'numeric';
        input.placeholder = 'Enter 5-digit ZIP';
        input.autocomplete = 'off';
        input.setAttribute('aria-label', 'Search ZIP Code');
        input.style.cssText = 'display:block;width:100%;box-sizing:border-box;margin-top:6px;padding:8px;border:1px solid #999;border-radius:4px;font:16px Arial,sans-serif;';
        var button = L.DomUtil.create('button', '', form);
        button.type = 'submit';
        button.textContent = 'Search';
        button.style.cssText = 'background:#333;color:white;border:0;border-radius:4px;padding:7px 12px;cursor:pointer;font:14px Arial,sans-serif;';
        var result = L.DomUtil.create('div', '', container);
        result.setAttribute('role', 'status');
        result.setAttribute('aria-live', 'polite');
        result.setAttribute('aria-atomic', 'true');
        result.style.cssText = 'margin-top:10px;';
        result.textContent = 'Enter a ZIP to see its boundary and team.';

        function resetSelection() {
            if (selectedLayer) {
                zipLayer.resetStyle(selectedLayer);
                selectedLayer = null;
            }
        }
        function search(showInvalid) {
            var zip = input.value.trim();
            resetSelection();
            result.replaceChildren();
            if (!/^\d{5}$/.test(zip)) {
                result.textContent = showInvalid && zip ? 'Enter a valid 5-digit ZIP code.' : 'Enter a ZIP to see its boundary and team.';
                return;
            }
            var layer = layersByZip[zip];
            if (!layer) {
                result.textContent = 'ZIP ' + zip + ' is not in this territory map.';
                return;
            }
            if (!map.hasLayer(zipLayer)) zipLayer.addTo(map);
            selectedLayer = layer;
            layer.setStyle({color: '#d7191c', weight: 5, opacity: 1, fillOpacity: 0});
            layer.bringToFront();
            map.fitBounds(layer.getBounds(), {padding: [40, 40], maxZoom: 13});
            var properties = layer.feature.properties;
            var location = L.DomUtil.create('div', '', result);
            location.textContent = 'ZIP ' + zip + (properties.City ? ' - ' + properties.City : '');
            var pm = L.DomUtil.create('strong', '', result);
            pm.style.cssText = 'display:block;margin-top:4px;font-size:16px;';
            var territory = String(properties.Territory || '').trim();
            pm.textContent = 'Team: ' + (territory.replace(/^PM\d+\s*-\s*/, '') || 'Not assigned');
        }
        form.addEventListener('submit', function (event) {
            event.preventDefault();
            search(true);
        });
        input.addEventListener('input', function () { search(false); });
        input.addEventListener('search', function () { search(false); });
        input.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                event.preventDefault();
                input.value = '';
                search(false);
            }
        });
        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.disableScrollPropagation(container);
        return container;
    };
    control.addTo(map);
    return control;
}
