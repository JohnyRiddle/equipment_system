(function () {
    const locationSelect = document.getElementById('id_location') || document.getElementById('id_to_location');
    const legalEntitySelect = document.getElementById('id_legal_entity');
    const costCenterSelect = document.getElementById('id_cost_center') || document.getElementById('id_to_cost_center');
    const warehouseSelect = document.getElementById('id_warehouse') || document.getElementById('id_to_warehouse');

    if (!locationSelect || !costCenterSelect) {
        return;
    }

    const currentCostCenter = costCenterSelect.value;
    const currentWarehouse = warehouseSelect ? warehouseSelect.value : '';

    function setCostCenterOptions(items, selectedValue) {
        costCenterSelect.innerHTML = '';

        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Выберите ЦФО';
        costCenterSelect.appendChild(placeholder);

        items.forEach(function (item) {
            const option = document.createElement('option');
            option.value = item.id;
            option.textContent = item.name;
            if (selectedValue && item.id === selectedValue) {
                option.selected = true;
            }
            costCenterSelect.appendChild(option);
        });
    }

    function loadCostCenters(selectedValue) {
        const params = new URLSearchParams();

        if (locationSelect.value) {
            params.set('location', locationSelect.value);
        }
        if (legalEntitySelect && legalEntitySelect.value) {
            params.set('legal_entity', legalEntitySelect.value);
        }

        fetch(`/app/ajax/cost-centers/?${params.toString()}`, {
            headers: {
                'Accept': 'application/json'
            }
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Unable to load cost centers.');
                }
                return response.json();
            })
            .then(function (data) {
                setCostCenterOptions(data.items || [], selectedValue);
            })
            .catch(function () {
                setCostCenterOptions([], '');
            });
    }

    function setWarehouseOptions(items, selectedValue) {
        if (!warehouseSelect) {
            return;
        }

        warehouseSelect.innerHTML = '';

        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Р’С‹Р±РµСЂРёС‚Рµ СЃРєР»Р°Рґ';
        warehouseSelect.appendChild(placeholder);

        items.forEach(function (item) {
            const option = document.createElement('option');
            option.value = item.id;
            option.textContent = item.name;
            if (selectedValue && item.id === selectedValue) {
                option.selected = true;
            }
            warehouseSelect.appendChild(option);
        });
    }

    function loadWarehouses(selectedValue) {
        if (!warehouseSelect) {
            return;
        }

        const params = new URLSearchParams();

        if (costCenterSelect.value) {
            params.set('cost_center', costCenterSelect.value);
        }

        fetch(`/app/ajax/warehouses/?${params.toString()}`, {
            headers: {
                'Accept': 'application/json'
            }
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Unable to load warehouses.');
                }
                return response.json();
            })
            .then(function (data) {
                setWarehouseOptions(data.items || [], selectedValue);
            })
            .catch(function () {
                setWarehouseOptions([], '');
            });
    }

    locationSelect.addEventListener('change', function () {
        loadCostCenters('');
        setWarehouseOptions([], '');
    });

    if (legalEntitySelect) {
        legalEntitySelect.addEventListener('change', function () {
            loadCostCenters('');
            setWarehouseOptions([], '');
        });
    }

    costCenterSelect.addEventListener('change', function () {
        loadWarehouses('');
    });

    if (locationSelect.value) {
        loadCostCenters(currentCostCenter);
    }

    if (costCenterSelect.value) {
        loadWarehouses(currentWarehouse);
    } else {
        setWarehouseOptions([], '');
    }
}());
