(function () {
    const form = document.querySelector('form[action$="/scan/"]');
    const input = document.querySelector('.inventory-scan-input');
    const button = document.getElementById('inventory-scan-camera-button');
    const cameraBox = document.getElementById('inventory-scan-camera');
    const video = document.getElementById('inventory-scan-video');
    const status = document.getElementById('inventory-scan-status');

    if (!form || !input || !button || !cameraBox || !video || !status) {
        return;
    }

    let stream = null;
    let stopped = true;

    function setStatus(text) {
        status.textContent = text;
    }

    function stopCamera() {
        stopped = true;
        if (stream) {
            stream.getTracks().forEach((track) => track.stop());
            stream = null;
        }
        video.srcObject = null;
        cameraBox.hidden = true;
        button.textContent = 'Сканировать камерой';
    }

    async function scanLoop(detector) {
        if (stopped) {
            return;
        }

        try {
            const codes = await detector.detect(video);
            if (codes.length > 0 && codes[0].rawValue) {
                input.value = codes[0].rawValue;
                stopCamera();
                form.submit();
                return;
            }
        } catch (error) {
            setStatus('Камера работает, но QR пока не найден. Для NFC используйте считыватель метки.');
        }

        window.requestAnimationFrame(() => scanLoop(detector));
    }

    async function startCamera() {
        if (!('BarcodeDetector' in window)) {
            setStatus('Браузер не поддерживает сканирование камерой. Используйте внешний сканер, NFC-считыватель или вставьте ссылку из метки.');
            cameraBox.hidden = false;
            return;
        }

        try {
            const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
            stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: 'environment' } },
                audio: false,
            });
            video.srcObject = stream;
            await video.play();
            stopped = false;
            cameraBox.hidden = false;
            button.textContent = 'Остановить камеру';
            setStatus('Наведите камеру на QR-код. Для NFC используйте считыватель метки.');
            scanLoop(detector);
        } catch (error) {
            stopCamera();
            cameraBox.hidden = false;
            setStatus('Не удалось включить камеру. Проверьте разрешение браузера или используйте внешний сканер/NFC-считыватель.');
        }
    }

    button.addEventListener('click', () => {
        if (stream) {
            stopCamera();
            return;
        }
        startCamera();
    });

    window.addEventListener('beforeunload', stopCamera);
}());
