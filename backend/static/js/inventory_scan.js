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

    const canvas = document.createElement('canvas');
    const canvasContext = canvas.getContext('2d', { willReadFrequently: true });
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
        button.textContent = 'Сканировать QR камерой';
    }

    function submitScanValue(value) {
        if (!value) {
            return false;
        }
        input.value = value;
        stopCamera();
        form.submit();
        return true;
    }

    function scanWithJsQr() {
        if (!window.jsQR || !canvasContext || video.readyState !== video.HAVE_ENOUGH_DATA) {
            return false;
        }

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvasContext.drawImage(video, 0, 0, canvas.width, canvas.height);
        const imageData = canvasContext.getImageData(0, 0, canvas.width, canvas.height);
        const code = window.jsQR(imageData.data, imageData.width, imageData.height, {
            inversionAttempts: 'dontInvert',
        });
        return code && submitScanValue(code.data);
    }

    async function scanWithBarcodeDetector(detector) {
        if (!detector) {
            return false;
        }
        const codes = await detector.detect(video);
        return codes.length > 0 && submitScanValue(codes[0].rawValue);
    }

    async function scanLoop(detector) {
        if (stopped) {
            return;
        }

        try {
            const foundByNativeDetector = await scanWithBarcodeDetector(detector);
            const foundByJsQr = foundByNativeDetector || scanWithJsQr();
            if (foundByJsQr) {
                return;
            }
        } catch (error) {
            scanWithJsQr();
        }

        if (!stopped) {
            setStatus('Камера работает, но QR пока не найден. Для NFC используйте считыватель метки.');
            window.requestAnimationFrame(() => scanLoop(detector));
        }
    }

    async function createDetector() {
        if (!('BarcodeDetector' in window)) {
            return null;
        }
        try {
            return new window.BarcodeDetector({ formats: ['qr_code'] });
        } catch (error) {
            return null;
        }
    }

    async function startCamera() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            cameraBox.hidden = false;
            setStatus('Браузер не дал доступ к камере. На iPhone откройте страницу по HTTPS или используйте внешний сканер/NFC-считыватель.');
            return;
        }

        if (!('BarcodeDetector' in window) && !window.jsQR) {
            cameraBox.hidden = false;
            setStatus('Сканирование камерой недоступно. Используйте внешний сканер, NFC-считыватель или вставьте ссылку из метки.');
            return;
        }

        try {
            const detector = await createDetector();
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
            setStatus('Не удалось включить камеру. На iPhone проверьте разрешение камеры и открывайте страницу по HTTPS.');
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
