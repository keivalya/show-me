/**
 * Show Me - Frontend (capture + describe flow).
 *
 * Flow: tap shutter -> Web Speech API listens -> stops on silence ->
 * capture frame + transcript -> POST /diagnose -> show steps + speak them.
 */

const DEBUG = true;
const API_BASE = `http://${window.location.hostname || 'localhost'}:8080`;

const state = {
    stream: null,
    mode: 'idle', // 'idle' | 'listening' | 'thinking' | 'results'
    recognition: null,
    transcript: '',
    fallbackTimer: null
};

const els = {
    video: document.getElementById('camera-preview'),
    shutter: document.getElementById('shutter-btn'),
    status: document.getElementById('status-text'),
    transcript: document.getElementById('transcript'),
    panel: document.getElementById('results-panel'),
    panelAppliance: document.getElementById('result-appliance'),
    panelSymptom: document.getElementById('result-symptom'),
    panelSummary: document.getElementById('result-summary'),
    panelSteps: document.getElementById('result-steps'),
    panelSafety: document.getElementById('result-safety'),
    panelSafetyList: document.getElementById('result-safety-list'),
    panelClose: document.getElementById('result-close'),
    canvas: document.createElement('canvas')
};

function log(...a) { if (DEBUG) console.log('[Show Me]', ...a); }

function setStatus(t) { els.status.innerText = t || ''; }

function setMode(m) {
    state.mode = m;
    els.shutter.classList.remove('listening', 'thinking');
    if (m === 'listening') els.shutter.classList.add('listening');
    if (m === 'thinking') els.shutter.classList.add('thinking');
    els.shutter.disabled = (m === 'thinking');
}

function showTranscript(t) {
    els.transcript.innerText = t || '';
    els.transcript.classList.toggle('hidden', !t);
}

async function initCamera() {
    try {
        log('Requesting camera + mic...');
        state.stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: 'environment',
                width: { ideal: 1280 },
                height: { ideal: 720 },
                frameRate: { ideal: 24 }
            },
            audio: true
        });
        els.video.srcObject = state.stream;
        log('Camera ready');
        setMode('idle');
        setStatus('Tap to capture and describe the problem');
    } catch (err) {
        log('Camera error:', err);
        setStatus('Camera & microphone permission required');
    }
}

function captureFrame() {
    const v = els.video;
    const w = v.videoWidth || 1280;
    const h = v.videoHeight || 720;
    els.canvas.width = w;
    els.canvas.height = h;
    els.canvas.getContext('2d').drawImage(v, 0, 0, w, h);
    return els.canvas.toDataURL('image/jpeg', 0.85).split(',')[1];
}

function startListening() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
        log('SpeechRecognition unavailable; using 5s timer fallback');
        setMode('listening');
        setStatus('Listening for 5 seconds…');
        state.transcript = '';
        state.fallbackTimer = setTimeout(() => {
            if (state.mode === 'listening') submitRequest();
        }, 5000);
        return;
    }

    const recog = new SR();
    recog.lang = 'en-US';
    recog.continuous = false;
    recog.interimResults = true;
    state.recognition = recog;
    state.transcript = '';

    recog.onstart = () => {
        log('SpeechRecognition started');
        setMode('listening');
        setStatus("Listening… describe what's wrong");
    };

    recog.onresult = (e) => {
        let interim = '', final = '';
        for (let i = 0; i < e.results.length; i++) {
            const r = e.results[i];
            if (r.isFinal) final += r[0].transcript;
            else interim += r[0].transcript;
        }
        state.transcript = (final || interim).trim();
        showTranscript(state.transcript);
    };

    recog.onerror = (e) => {
        log('SR error:', e.error);
        if (state.mode === 'listening') {
            // 'no-speech' or 'aborted' is OK; just submit whatever we have (if any)
            submitRequest();
        }
    };

    recog.onend = () => {
        log('SR ended. Final transcript:', state.transcript);
        if (state.mode === 'listening') submitRequest();
    };

    try {
        recog.start();
    } catch (err) {
        log('SR start failed:', err);
        setStatus('Could not start listening. Tap to retry.');
        setMode('idle');
    }
}

function cancelListening() {
    if (state.recognition) {
        try { state.recognition.abort(); } catch (e) {}
        state.recognition = null;
    }
    if (state.fallbackTimer) {
        clearTimeout(state.fallbackTimer);
        state.fallbackTimer = null;
    }
}

async function submitRequest() {
    cancelListening();
    setMode('thinking');
    setStatus('Diagnosing…');

    const image_base64 = captureFrame();
    const transcript = state.transcript || '';
    log('Submitting. Transcript:', transcript, 'image bytes (b64):', image_base64.length);

    try {
        const res = await fetch(`${API_BASE}/diagnose`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image_base64, transcript })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        log('Diagnose result:', data);
        if (data.error) throw new Error(data.error);
        showResults(data);
    } catch (err) {
        log('Diagnose failed:', err);
        setStatus('Error: ' + err.message + ' — tap to try again');
        setMode('idle');
    }
}

function showResults(d) {
    setMode('results');
    setStatus('');
    showTranscript('');

    els.panelAppliance.innerText = d.appliance || 'Diagnosis';
    if (d.symptom) {
        els.panelSymptom.innerText = d.symptom;
        els.panelSymptom.classList.remove('hidden');
    } else {
        els.panelSymptom.classList.add('hidden');
    }
    els.panelSummary.innerText = d.summary || '';

    els.panelSteps.innerHTML = '';
    (d.steps || []).forEach((s) => {
        const li = document.createElement('li');
        li.innerText = s;
        els.panelSteps.appendChild(li);
    });

    if (d.safety_notes && d.safety_notes.length) {
        els.panelSafety.classList.remove('hidden');
        els.panelSafetyList.innerHTML = '';
        d.safety_notes.forEach((n) => {
            const li = document.createElement('li');
            li.innerText = n;
            els.panelSafetyList.appendChild(li);
        });
    } else {
        els.panelSafety.classList.add('hidden');
    }

    els.panel.classList.remove('hidden');
    // Defer the transform so the transition runs
    requestAnimationFrame(() => els.panel.classList.add('open'));

    speakDiagnosis(d);
}

function speakDiagnosis(d) {
    if (!('speechSynthesis' in window)) return;
    const lines = [];
    if (d.summary) lines.push(d.summary);
    (d.steps || []).forEach((s, i) => lines.push(`Step ${i + 1}: ${s}`));
    if (d.safety_notes && d.safety_notes.length) {
        lines.push('A safety note:');
        d.safety_notes.forEach((n) => lines.push(n));
    }
    if (!lines.length) return;
    const u = new SpeechSynthesisUtterance(lines.join('. '));
    u.rate = 1.0;
    u.pitch = 1.0;
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
}

function reset() {
    els.panel.classList.remove('open');
    setTimeout(() => els.panel.classList.add('hidden'), 350);
    showTranscript('');
    state.transcript = '';
    if ('speechSynthesis' in window) speechSynthesis.cancel();
    setMode('idle');
    setStatus('Tap to capture and describe the problem');
}

els.shutter.addEventListener('click', () => {
    if (state.mode === 'idle') {
        startListening();
    } else if (state.mode === 'listening') {
        // User taps again -> commit early
        if (state.recognition) {
            try { state.recognition.stop(); } catch (e) {}
        } else {
            submitRequest();
        }
    }
    // 'thinking' and 'results' modes ignore taps (use Done button to reset)
});

els.panelClose.addEventListener('click', reset);

window.addEventListener('DOMContentLoaded', initCamera);
