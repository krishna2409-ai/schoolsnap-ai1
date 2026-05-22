import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const abs = (p: string) => (p.startsWith('http') ? p : `${API}${p}`);

type Session = { token: string; registration_number: string; parent_name: string; child_id: string; child_name: string; email?: string; phone?: string };
type Match = { id: string; preview_url: string; confidence_pct: number; source: string };

function blob(c: HTMLCanvasElement): Promise<Blob> {
  return new Promise((r, e) => c.toBlob(b => (b ? r(b) : e(new Error('fail'))), 'image/jpeg', 0.92));
}

/* ── Clean Header ── */
function Header({ title, onBack }: { title: string; onBack?: () => void }) {
  return (
    <header className="v1-header">
      <div className="v1-header-left">
        {onBack && <button className="v1-back" onClick={onBack}>←</button>}
        <h1>{title}</h1>
      </div>
      <div className="v1-brand">SchoolSnap</div>
    </header>
  );
}

/* ══════════════════════════════════════════════════════════════════ */
/* LOGIN                                                              */
/* ══════════════════════════════════════════════════════════════════ */
function LoginPage({ onLogin }: { onLogin: (s: Session) => void }) {
  const [reg, setReg] = useState('');
  const [dob, setDob] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(''); setBusy(true);
    const fd = new FormData();
    fd.append('registration_number', reg.trim());
    fd.append('dob', dob.trim());
    try {
      const r = await fetch(`${API}/parent-login`, { method: 'POST', body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail ?? 'Login failed');
      onLogin(d);
    } catch (x) {
      setErr(x instanceof Error ? x.message : 'Login failed');
    } finally { setBusy(false); }
  };

  return (
    <div className="v1-layout">
      <Header title="Parent Portal" />
      <main className="v1-center">
        <div className="v1-login-hero">
          <div className="v1-logo-circle">📸</div>
          <h2>Welcome to SchoolSnap</h2>
          <p>Access your child's event photos securely</p>
        </div>

        <form className="v1-card v1-form" onSubmit={submit}>
          <label>
            <span>Registration Number</span>
            <input id="v1-reg" value={reg} onChange={e => setReg(e.target.value)} required placeholder="e.g. REG1001" />
          </label>
          <label>
            <span>Date of Birth</span>
            <input id="v1-dob" type="date" value={dob} onChange={e => setDob(e.target.value)} required />
          </label>
          {err && <div className="v1-error">{err}</div>}
          <button type="submit" disabled={busy} className="v1-btn-primary">
            {busy ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="v1-demo-hint">
          <span>Demo:</span> REG1001 / 2014-05-12
        </div>
      </main>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════ */
/* SCANNER + RESULTS                                                  */
/* ══════════════════════════════════════════════════════════════════ */
function ScannerPage({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [status, setStatus] = useState<'idle' | 'scanning' | 'hologram' | 'found' | 'none'>('idle');
  const [msg, setMsg] = useState('');
  const [matches, setMatches] = useState<Match[]>([]);
  const [camErr, setCamErr] = useState('');
  const [selected, setSelected] = useState<Match | null>(null);
  const [purchased, setPurchased] = useState<Set<string>>(new Set());
  const [payStep, setPayStep] = useState<'info' | 'otp' | 'done'>('info');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [otpErr, setOtpErr] = useState('');

  // Live Toast System
  type Toast = { id: string; msg: string; type: 'success' | 'error' | 'info' };
  const [toasts, setToasts] = useState<Toast[]>([]);
  const showToast = useCallback((msg: string, type: 'success' | 'error' | 'info' = 'info') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts(prev => [...prev, { id, msg, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3000);
  }, []);

  // Operation Console Log System
  type LogLine = { id: string; time: string; text: string; type: 'info' | 'success' | 'warn' | 'error' };
  const [logs, setLogs] = useState<LogLine[]>([]);
  const logConsoleRef = useRef<HTMLDivElement>(null);
  const addLog = useCallback((text: string, type: 'info' | 'success' | 'warn' | 'error' = 'info') => {
    const id = Math.random().toString(36).substring(2, 9);
    const time = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, { id, time, text, type }]);
  }, []);

  useEffect(() => {
    if (logConsoleRef.current) {
      logConsoleRef.current.scrollTop = logConsoleRef.current.scrollHeight;
    }
  }, [logs]);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  const holoCanvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const busyRef = useRef(false);

  const stopCam = useCallback(() => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
  }, []);

  const doScan = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current || busyRef.current) return;
    busyRef.current = true;
    addLog('Acquiring camera frame...', 'info');
    try {
      const c = canvasRef.current, v = videoRef.current;
      if (v.readyState < 2) return;
      c.width = v.videoWidth || 720; c.height = v.videoHeight || 720;
      const ctx = c.getContext('2d'); if (!ctx) return;
      ctx.drawImage(v, 0, 0, c.width, c.height);
      const b = await blob(c);
      const fd = new FormData();
      fd.append('token', session.token); fd.append('file', b, 'scan.jpg');
      
      addLog('Transmitting biometric vector signature to search node...', 'info');
      const r = await fetch(`${API}/parent/scan-and-match`, { method: 'POST', body: fd });
      if (!r.ok) {
        addLog('Search node returned non-200 response.', 'error');
        return;
      }
      const d = await r.json();
      if (d.status === 'green' && d.matches?.length > 0) {
        if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
        addLog('BIOMETRIC RETRIEVAL DETECTED MATCHES!', 'success');
        addLog('Reconstructing biometric mesh...', 'info');
        showToast('Face pattern recognized!', 'success');
        
        setStatus('hologram');
        setTimeout(() => {
          setStatus('found');
          setMsg(d.message);
          setMatches(d.matches);
          addLog(`Indexed matches returned: ${d.matches.length} photos.`, 'success');
          showToast(`Retrieved ${d.matches.length} photo matches!`, 'success');
        }, 1200);
      } else {
        setStatus('scanning');
        setMsg(d.message || 'Scanning...');
        addLog(`Scan cycle complete. Result: ${d.message || 'Face not recognized'}`, 'warn');
      }
    } catch {
      addLog('Biometric transmission pipeline interrupted.', 'error');
    }
    finally { busyRef.current = false; }
  }, [session, addLog, showToast]);

  const startCam = useCallback(async () => {
    if (!videoRef.current) return;
    setCamErr('');
    addLog('Initializing biometric extraction hardware...', 'info');
    try {
      stopCam();
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 480 }, height: { ideal: 480 } } });
      streamRef.current = s; videoRef.current.srcObject = s; await videoRef.current.play();
      setStatus('scanning'); setMsg('Position face in frame...');
      addLog('Camera feed active. Model is tracking.', 'success');
      showToast('Biometric scanner initialized', 'info');
      
      setTimeout(() => {
        intervalRef.current = setInterval(() => void doScan(), 3500);
        void doScan();
      }, 1500);
    } catch { 
      setCamErr('Simulating virtual scan for demo...');
      setStatus('scanning'); setMsg('Scanning virtual face...');
      addLog('Optical capture hardware bypassed. Emulating virtual scanner...', 'warn');
      showToast('Camera denied. Simulating mock data...', 'info');
      
      // MOCK MATCH FOR VIDEO
      setTimeout(() => {
        addLog('Analyzing simulated depth pattern...', 'info');
        setStatus('hologram');
        setTimeout(() => {
          setStatus('found'); setMsg('Matches found successfully!'); 
          setMatches([
            { id: 'mock1', preview_url: '/images/previews/evt101.jpg', confidence_pct: 95.4, source: 'evt101.jpg' },
            { id: 'mock2', preview_url: '/images/previews/evt102.jpg', confidence_pct: 88.2, source: 'evt102.jpg' }
          ]);
          setCamErr('');
          addLog('Simulated face authorization successful!', 'success');
          showToast('Mock biometric scan complete!', 'success');
        }, 1200);
      }, 3000);
    }
  }, [stopCam, doScan, addLog, showToast]);

  useEffect(() => { void startCam(); return () => stopCam(); }, [startCam, stopCam]);

  useEffect(() => {
    if (videoRef.current && streamRef.current && !videoRef.current.srcObject) {
      videoRef.current.srcObject = streamRef.current;
      void videoRef.current.play().catch(() => {});
    }
  }, [selected]);

  const rescan = () => {
    stopCam();
    addLog('Resetting biometric search caches...', 'warn');
    showToast('Rescanning initiated...', 'info');
    setMatches([]);
    setStatus('idle');
    setMsg('Ready to scan');
    setTimeout(() => {
      void startCam();
    }, 100);
  };

  const handleSkipScan = async () => {
    stopCam();
    addLog('MANUAL OVERRIDE TRIGGERED', 'warn');
    addLog('Compiling custom bypass token...', 'info');
    showToast('Bypass activated! Mapping vectors...', 'info');
    setStatus('hologram');
    
    setTimeout(() => addLog('Holographic matrix constructed.', 'info'), 300);
    setTimeout(() => addLog('Resolving depth mesh (812 mapped nodes)...', 'info'), 600);
    setTimeout(() => addLog('Scanning database index nodes...', 'info'), 900);

    try {
      const fd = new FormData();
      fd.append('token', session.token);
      
      const r = await fetch(`${API}/parent/bypass-scan`, { method: 'POST', body: fd });
      const d = await r.json();
      
      if (!r.ok) {
        throw new Error(d.detail ?? 'Bypass search failed');
      }
      
      setTimeout(() => {
        setStatus('found');
        setMsg(d.message || 'Demo Mode: Face Scan Bypassed');
        setMatches(d.matches || []);
        addLog(`Bypass completed. ${d.matches?.length || 0} photo fragments decrypted.`, 'success');
        showToast(d.message || 'Bypass successful!', 'success');
      }, 1200);
    } catch (x) {
      setTimeout(() => {
        setStatus('idle');
        const errMsg = x instanceof Error ? x.message : 'Bypass failed';
        addLog(`Bypass pipeline failed: ${errMsg}`, 'error');
        showToast(errMsg, 'error');
      }, 1200);
    }
  };

  /* Canvas animation for Scanning Overlay */
  useEffect(() => {
    if (status !== 'scanning' || !videoRef.current || !overlayCanvasRef.current) return;
    const canvas = overlayCanvasRef.current;
    const video = videoRef.current;
    let active = true;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Create a small 40x30 in-memory temp canvas
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = 40;
    tempCanvas.height = 30;
    const tempCtx = tempCanvas.getContext('2d');

    let smoothX = 0.5;
    let smoothY = 0.5;
    let smoothW = 0.35;
    let smoothH = 0.45;
    let initialized = false;
    let angle = 0;

    const relativeLandmarks = [
      // Jawline (0-8)
      { x: -0.35, y: -0.2, group: 'jaw' },
      { x: -0.3, y: 0.05, group: 'jaw' },
      { x: -0.22, y: 0.25, group: 'jaw' },
      { x: -0.12, y: 0.38, group: 'jaw' },
      { x: 0, y: 0.42, group: 'jaw' },
      { x: 0.12, y: 0.38, group: 'jaw' },
      { x: 0.22, y: 0.25, group: 'jaw' },
      { x: 0.3, y: 0.05, group: 'jaw' },
      { x: 0.35, y: -0.2, group: 'jaw' },

      // Left Eyebrow (9-12)
      { x: -0.25, y: -0.32, group: 'l_brow' },
      { x: -0.18, y: -0.37, group: 'l_brow' },
      { x: -0.1, y: -0.35, group: 'l_brow' },
      { x: -0.04, y: -0.3, group: 'l_brow' },

      // Right Eyebrow (13-16)
      { x: 0.04, y: -0.3, group: 'r_brow' },
      { x: 0.1, y: -0.35, group: 'r_brow' },
      { x: 0.18, y: -0.37, group: 'r_brow' },
      { x: 0.25, y: -0.32, group: 'r_brow' },

      // Left Eye (17-20)
      { x: -0.22, y: -0.18, group: 'l_eye' },
      { x: -0.17, y: -0.21, group: 'l_eye' },
      { x: -0.12, y: -0.18, group: 'l_eye' },
      { x: -0.17, y: -0.15, group: 'l_eye' },

      // Right Eye (21-24)
      { x: 0.12, y: -0.18, group: 'r_eye' },
      { x: 0.17, y: -0.21, group: 'r_eye' },
      { x: 0.22, y: -0.18, group: 'r_eye' },
      { x: 0.17, y: -0.15, group: 'r_eye' },

      // Nose Bridge (25-27)
      { x: 0, y: -0.25, group: 'nose_br' },
      { x: 0, y: -0.1, group: 'nose_br' },
      { x: 0, y: 0.02, group: 'nose_br' },

      // Nose Base (28-30)
      { x: -0.07, y: 0.08, group: 'nose_bs' },
      { x: 0, y: 0.11, group: 'nose_bs' },
      { x: 0.07, y: 0.08, group: 'nose_bs' },

      // Mouth (31-33)
      { x: -0.12, y: 0.23, group: 'mouth' },
      { x: 0, y: 0.27, group: 'mouth' },
      { x: 0.12, y: 0.23, group: 'mouth' }
    ];

    const render = () => {
      if (!active) return;
      const rect = video.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        if (canvas.width !== rect.width || canvas.height !== rect.height) {
          canvas.width = rect.width;
          canvas.height = rect.height;
        }
      }

      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      let targetX = 0.5;
      let targetY = 0.5;
      let targetW = 0.35;
      let targetH = 0.45;
      let detected = false;

      // Skin tone tracking
      if (video.readyState >= 2 && tempCtx) {
        try {
          tempCtx.drawImage(video, 0, 0, 40, 30);
          const imgData = tempCtx.getImageData(0, 0, 40, 30);
          const data = imgData.data;

          let sumX = 0;
          let sumY = 0;
          let count = 0;
          let minX = 40, maxX = 0, minY = 30, maxY = 0;

          for (let y = 0; y < 30; y++) {
            for (let x = 0; x < 40; x++) {
              const idx = (y * 40 + x) * 4;
              const r = data[idx];
              const g = data[idx + 1];
              const b = data[idx + 2];
              
              const max = Math.max(r, g, b);
              const min = Math.min(r, g, b);
              
              // Skin chrominance threshold rules
              if (r > 70 && g > 45 && b > 30 && r > g && r > b && (max - min) > 12 && (r - g) > 12) {
                sumX += x;
                sumY += y;
                count++;
                if (x < minX) minX = x;
                if (x > maxX) maxX = x;
                if (y < minY) minY = y;
                if (y > maxY) maxY = y;
              }
            }
          }

          if (count > 8) {
            detected = true;
            const cx = (sumX / count) / 40;
            const cy = (sumY / count) / 30;
            const rw = (maxX - minX + 1) / 40;
            const rh = (maxY - minY + 1) / 30;

            targetX = cx;
            targetY = cy;
            targetW = Math.max(0.2, Math.min(0.6, rw * 1.5));
            targetH = Math.max(0.25, Math.min(0.8, rh * 1.5));
          }
        } catch (e) {
          // ignore canvas access errors if stream isn't fully ready
        }
      }

      if (!detected) {
        targetX = 0.5;
        targetY = 0.5;
        const time = Date.now() * 0.002;
        targetW = 0.35 + Math.sin(time) * 0.02;
        targetH = 0.45 + Math.sin(time) * 0.02;
      }

      if (!initialized) {
        smoothX = targetX;
        smoothY = targetY;
        smoothW = targetW;
        smoothH = targetH;
        initialized = true;
      } else {
        smoothX = smoothX * 0.85 + targetX * 0.15;
        smoothY = smoothY * 0.85 + targetY * 0.15;
        smoothW = smoothW * 0.85 + targetW * 0.15;
        smoothH = smoothH * 0.85 + targetH * 0.15;
      }

      const pxX = smoothX * w;
      const pxY = smoothY * h;
      const pxW = smoothW * w;
      const pxH = smoothH * h;

      // Oval Face Guide - Let oval dynamically scale and track smoothX/smoothY/smoothW/smoothH for a seamless holographic UX
      ctx.strokeStyle = 'rgba(99, 102, 241, 0.35)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 6]);
      ctx.beginPath();
      ctx.ellipse(pxX, pxY, pxW * 0.6, pxH * 0.7, 0, 0, 2 * Math.PI);
      ctx.stroke();
      ctx.setLineDash([]);

      // Generate facial landmarks with slight micro-jitter
      const jitterAmount = 0.004;
      const mappedPoints = relativeLandmarks.map(p => {
        const jitterX = (Math.random() - 0.5) * jitterAmount * pxW;
        const jitterY = (Math.random() - 0.5) * jitterAmount * pxH;
        return {
          x: pxX + p.x * pxW + jitterX,
          y: pxY + p.y * pxH + jitterY,
          group: p.group
        };
      });

      // Connected Vector Lines
      ctx.strokeStyle = 'rgba(99, 102, 241, 0.4)';
      ctx.lineWidth = 1;
      
      const drawLine = (p1: typeof mappedPoints[0], p2: typeof mappedPoints[0]) => {
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();
      };

      // 1. Jawline
      for (let i = 0; i < 8; i++) drawLine(mappedPoints[i], mappedPoints[i+1]);
      // 2. Left Eyebrow
      for (let i = 9; i < 12; i++) drawLine(mappedPoints[i], mappedPoints[i+1]);
      // 3. Right Eyebrow
      for (let i = 13; i < 16; i++) drawLine(mappedPoints[i], mappedPoints[i+1]);
      // 4. Left Eye
      for (let i = 17; i < 20; i++) drawLine(mappedPoints[i], mappedPoints[i+1]);
      drawLine(mappedPoints[20], mappedPoints[17]);
      // 5. Right Eye
      for (let i = 21; i < 24; i++) drawLine(mappedPoints[i], mappedPoints[i+1]);
      drawLine(mappedPoints[24], mappedPoints[21]);
      // 6. Nose Bridge
      for (let i = 25; i < 27; i++) drawLine(mappedPoints[i], mappedPoints[i+1]);
      // 7. Nose Base
      for (let i = 28; i < 30; i++) drawLine(mappedPoints[i], mappedPoints[i+1]);
      // 8. Mouth
      for (let i = 31; i < 33; i++) drawLine(mappedPoints[i], mappedPoints[i+1]);

      // Cross-group mesh links
      drawLine(mappedPoints[10], mappedPoints[18]);
      drawLine(mappedPoints[15], mappedPoints[22]);
      drawLine(mappedPoints[26], mappedPoints[19]);
      drawLine(mappedPoints[26], mappedPoints[21]);
      drawLine(mappedPoints[27], mappedPoints[29]);
      drawLine(mappedPoints[29], mappedPoints[32]);
      drawLine(mappedPoints[31], mappedPoints[3]);
      drawLine(mappedPoints[33], mappedPoints[5]);

      // Pulsing circular node points
      const pulseRadius = 2.5 + Math.sin(Date.now() * 0.01) * 0.8;
      ctx.fillStyle = 'rgba(129, 140, 248, 0.85)';
      mappedPoints.forEach(p => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, pulseRadius, 0, 2 * Math.PI);
        ctx.fill();
      });

      // Viewport Corner Brackets
      const pad = 24;
      const len = 16;
      ctx.strokeStyle = '#6366f1';
      ctx.lineWidth = 2.5;

      ctx.beginPath();
      ctx.moveTo(pad, pad + len); ctx.lineTo(pad, pad); ctx.lineTo(pad + len, pad);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(w - pad, pad + len); ctx.lineTo(w - pad, pad); ctx.lineTo(w - pad - len, pad);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(pad, h - pad - len); ctx.lineTo(pad, h - pad); ctx.lineTo(pad + len, h - pad);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(w - pad, h - pad - len); ctx.lineTo(w - pad, h - pad); ctx.lineTo(w - pad - len, h - pad);
      ctx.stroke();

      // Telemetry ring tracking the face center
      angle += 0.02;
      ctx.strokeStyle = 'rgba(99, 102, 241, 0.45)';
      ctx.beginPath();
      ctx.arc(pxX, pxY, pxW * 0.35, angle, angle + 1.2);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(pxX, pxY, pxW * 0.35, angle + Math.PI, angle + Math.PI + 1.2);
      ctx.stroke();

      // Crosshairs tracking the face center
      ctx.strokeStyle = 'rgba(99, 102, 241, 0.25)';
      ctx.beginPath();
      ctx.moveTo(pxX - 12, pxY); ctx.lineTo(pxX + 12, pxY);
      ctx.moveTo(pxX, pxY - 12); ctx.lineTo(pxX, pxY + 12);
      ctx.stroke();

      // Digital labels
      ctx.fillStyle = '#818cf8';
      ctx.font = '8px Courier New, monospace';
      ctx.fillText('FACIAL_SCAN_AETHER_V1', pad, pad - 6);
      ctx.fillText('FAISS_LOCK: ACTIVE', w - pad - 100, pad - 6);
      ctx.fillText(`YAW: ${(Math.sin(angle) * 15).toFixed(1)}deg`, pad, h - pad + 12);
      ctx.fillText('ENCRYPT: SECURE_MD5', w - pad - 100, h - pad + 12);

      requestAnimationFrame(render);
    };

    render();
    return () => { active = false; };
  }, [status]);

  // Canvas animation for 1.2s Hologram Scan on Bypass
  useEffect(() => {
    if (status !== 'hologram' || !holoCanvasRef.current) return;
    const canvas = holoCanvasRef.current;
    canvas.width = 300;
    canvas.height = 200;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let active = true;
    let frame = 0;

    const points: { x: number; y: number; z: number }[] = [];
    for (let lat = -5; lat <= 5; lat++) {
      for (let lon = -5; lon <= 5; lon++) {
        const x = lon * 20;
        const y = lat * 20;
        const z = Math.sqrt(Math.max(0, 10000 - x*x - y*y)) * 0.75;
        points.push({ x, y, z });
      }
    }

    const render = () => {
      if (!active) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const cx = canvas.width / 2;
      const cy = canvas.height / 2;

      const angleX = frame * 0.05;
      const angleY = frame * 0.07;

      ctx.strokeStyle = 'rgba(99, 102, 241, 0.45)';
      ctx.fillStyle = '#818cf8';
      ctx.lineWidth = 1;

      points.forEach((p, idx) => {
        let x1 = p.x * Math.cos(angleY) - p.z * Math.sin(angleY);
        let z1 = p.x * Math.sin(angleY) + p.z * Math.cos(angleY);

        let y2 = p.y * Math.cos(angleX) - z1 * Math.sin(angleX);
        let z2 = p.y * Math.sin(angleX) + z1 * Math.cos(angleX);

        const dist = 320;
        const scale = dist / (dist + z2);
        const projX = cx + x1 * scale;
        const projY = cy + y2 * scale;

        ctx.beginPath();
        ctx.arc(projX, projY, 2, 0, 2 * Math.PI);
        ctx.fill();

        if (idx % 11 !== 10) {
          const nextPt = points[idx + 1];
          let nx1 = nextPt.x * Math.cos(angleY) - nextPt.z * Math.sin(angleY);
          let nz1 = nextPt.x * Math.sin(angleY) + nextPt.z * Math.cos(angleY);
          let ny2 = nextPt.y * Math.cos(angleX) - nz1 * Math.sin(angleX);
          const nprojX = cx + nx1 * scale;
          const nprojY = cy + ny2 * scale;

          ctx.beginPath();
          ctx.moveTo(projX, projY);
          ctx.lineTo(nprojX, nprojY);
          ctx.stroke();
        }
      });

      ctx.strokeStyle = 'rgba(99, 102, 241, 0.25)';
      ctx.beginPath();
      ctx.arc(cx, cy, 60 + Math.sin(frame * 0.2) * 12, 0, 2 * Math.PI);
      ctx.stroke();

      frame++;
      requestAnimationFrame(render);
    };

    render();
    return () => { active = false; };
  }, [status]);

  /* ── Purchase flow ── */
  const openPurchase = (m: Match) => {
    addLog(`Accessing asset node details for target: ${m.id}`, 'info');
    setSelected(m); setPayStep(purchased.has(m.id) ? 'done' : 'info');
    setEmail(session.email || ''); setPhone(session.phone || ''); setOtp(''); setOtpErr('');
  };
  const closePurchase = () => {
    addLog('Returning to global matches overview.', 'info');
    setSelected(null); setPayStep('info');
  };

  const submitPayment = (e: FormEvent) => {
    e.preventDefault();
    addLog(`INITIATED SECURE CARD TRANSACTION FOR ${email || 'holder'}`, 'info');
    addLog('Contacting gateway terminal...', 'info');
    showToast('Contacting payment gateway...', 'info');
    setTimeout(() => {
      setPayStep('otp');
      addLog('Transaction authorized by gateway. One-Time Passcode requested.', 'warn');
      addLog('SMS and Email notification transmission completed.', 'success');
      showToast('OTP transmitted! Please check phone.', 'success');
    }, 800);
  };

  const verifyOtp = (e: FormEvent) => {
    e.preventDefault();
    addLog(`VERIFYING SECURE KEY FOR REFERENCE: SS-847293`, 'info');
    if (otp.trim() === '847293') {
      addLog('CRYPTOGRAPHIC KEY AUTHENTICATED SUCCESSFULLY.', 'success');
      showToast('Payment authenticated!', 'success');
      setPayStep('done');
      setOtpErr('');
      if (selected) {
        setPurchased(prev => new Set([...prev, selected.id]));
        addLog(`High-res unlock certificate granted for ${selected.id}.`, 'success');
      }
    } else {
      addLog('SECURITY ERROR: CODE MISMATCH DETECTED.', 'error');
      showToast('Invalid passcode. Try again.', 'error');
      setOtpErr('Invalid code');
    }
  };

  const downloadPhoto = () => {
    if (!selected) return;
    addLog(`Initiating raw blob payload download: ${selected.id}`, 'info');
    showToast('Downloading high-res photo...', 'success');
    const a = document.createElement('a');
    a.href = abs(selected.preview_url); a.download = `SchoolSnap_${selected.id}.jpg`;
    a.target = '_blank'; document.body.appendChild(a); a.click(); document.body.removeChild(a);
  };

  /* ── Purchase overlay ── */
  if (selected) {
    return (
      <div className="v1-layout">
        <Header title="Photo Details" onBack={closePurchase} />
        <main className="v1-center">
          <div className="v1-card v1-photo-detail">
            <div className={`v1-photo-preview ${payStep === 'done' ? 'unlocked' : ''}`}>
              <img src={abs(selected.preview_url)} alt="Photo" />
              {payStep !== 'done' && <div className="v1-watermark">SCHOOLSNAP</div>}
            </div>

            <div className="v1-purchase-steps">
              <div className={`v1-step ${payStep === 'info' ? 'active' : 'complete'}`}>1. Pay</div>
              <div className="v1-step-line" />
              <div className={`v1-step ${payStep === 'otp' ? 'active' : payStep === 'done' ? 'complete' : ''}`}>2. Verify</div>
              <div className="v1-step-line" />
              <div className={`v1-step ${payStep === 'done' ? 'active' : ''}`}>3. Download</div>
            </div>

            {/* HIGH-TECH 3D ROTATING CREDIT CARD / OTP SECURE CODE */}
            {payStep !== 'done' && (
              <div className="payment-flip-container">
                <div className={`payment-flip-inner ${payStep === 'otp' ? 'flipped' : ''}`}>
                  
                  {/* FRONT SIDE (Credit Card Details) */}
                  <div className="payment-card-front">
                    <div className="payment-card-glow" />
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div className="payment-card-chip" />
                      <span className="payment-card-logo">SchoolSnap Secure Pay</span>
                    </div>
                    <div>
                      <div style={{ fontFamily: 'monospace', fontSize: '1rem', letterSpacing: '0.15em', marginBottom: '0.35rem' }}>
                        •••• •••• •••• 8472
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', opacity: 0.8 }}>
                        <span>CARDHOLDER: SECURE PARENT</span>
                        <span>EXP: 09/29</span>
                      </div>
                    </div>
                  </div>

                  {/* BACK SIDE (OTP Security Key Details) */}
                  <div className="payment-card-back">
                    <div className="payment-card-glow" />
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.7rem', fontWeight: 'bold', color: 'var(--v1-accent-light)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>OTP SECURITY ACCESS</span>
                      <span className="payment-card-logo">SECURE SHIELD</span>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.5)', padding: '0.5rem', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.05)', textAlign: 'center' }}>
                      <span style={{ fontSize: '0.8rem', opacity: 0.9, fontFamily: 'monospace', letterSpacing: '0.05em' }}>GATEWAY KEYPAD ACTIVE</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.65rem', opacity: 0.6 }}>Reference ID: SS-847293</span>
                      <span style={{ color: 'var(--v1-success)', fontWeight: 'bold', fontSize: '0.7rem' }}>🔐 SECURE KEY</span>
                    </div>
                  </div>

                </div>
              </div>
            )}

            {payStep === 'info' && (
              <form className="v1-form" onSubmit={submitPayment}>
                <div className="v1-price">₹149 <span>per photo</span></div>
                <label><span>Email</span><input type="email" value={email} onChange={e => setEmail(e.target.value)} required placeholder="your@email.com" /></label>
                <label><span>Phone</span><input type="tel" value={phone} onChange={e => setPhone(e.target.value)} required placeholder="+91 90000 00000" /></label>
                <button type="submit" className="v1-btn-primary">Pay ₹149</button>
              </form>
            )}

            {payStep === 'otp' && (
              <form className="v1-form" onSubmit={verifyOtp}>
                <p className="v1-otp-sent">OTP sent to {phone || email}</p>
                <label><span>Enter OTP</span><input type="text" maxLength={6} value={otp} onChange={e => setOtp(e.target.value)} required placeholder="000000" className="v1-otp-input" /></label>
                {otpErr && <div className="v1-error">{otpErr}</div>}
                <button type="submit" className="v1-btn-primary">Verify</button>
                <p className="v1-hint">Demo OTP: 847293</p>
              </form>
            )}

            {payStep === 'done' && (
              <div className="v1-success-actions">
                <div className="v1-success-msg">✓ Payment verified</div>
                <button className="v1-btn-primary" onClick={downloadPhoto}>Download High-Res Photo</button>
                <button className="v1-btn-ghost" onClick={closePurchase}>← Back to Gallery</button>
              </div>
            )}


          </div>
        </main>

        {/* Global Toast System Portal */}
        <div className="toast-container">
          {toasts.map(t => (
            <div key={t.id} className={`toast-alert ${t.type}`}>
              <span className="toast-icon">{t.type === 'success' ? '✓' : t.type === 'error' ? '✕' : 'ℹ'}</span>
              <span>{t.msg}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  /* ── Scanner + Gallery ── */
  return (
    <div className="v1-layout">
      <Header title={`${session.child_name}'s Photos`} onBack={onLogout} />
      <main className="v1-shell">
        {/* Camera */}
        <section className="v1-card v1-scanner-card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div className="v1-cam-viewport">
            <video ref={videoRef} playsInline muted className="v1-cam-video" />
            {status === 'scanning' && <canvas ref={overlayCanvasRef} className="v1-cam-overlay" />}
            {status === 'hologram' && (
              <div className="holographic-bypass-container">
                <div className="holographic-title">HOLOGRAPHIC VECTOR SCAN</div>
                <canvas ref={holoCanvasRef} className="holographic-canvas" />
                <div className="holographic-terminal">
                  <div style={{ color: '#4ade80' }}>⚡ BYPASS MODE ONGOING</div>
                  <div>- RETRIEVING 3D SHIELD KEYS...</div>
                  <div>- SCANNING FAISS INDICES...</div>
                </div>
              </div>
            )}
            {status === 'scanning' && <div className="v1-scan-line" />}
            {camErr && <div className="v1-cam-error">{camErr}</div>}
          </div>
          <div className="v1-scan-status" style={{ marginBottom: status === 'scanning' ? '12px' : '0' }}>
            <span className={`v1-status-dot ${status}`} />
            <span>{msg || 'Ready to scan'}</span>
          </div>
          {status === 'scanning' && (
            <button 
              type="button" 
              className="v1-btn-ghost" 
              onClick={handleSkipScan}
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: '8px',
                border: '1px dashed #3b82f6',
                background: 'rgba(59, 130, 246, 0.08)',
                color: '#60a5fa',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '0.9rem',
                textAlign: 'center',
                transition: 'all 0.2s ease',
              }}
            >
              ⚡ Demo Mode: Skip Face Scan
            </button>
          )}
        </section>

        {/* Results */}
        <section className="v1-results-section">
          <div className="v1-results-header">
            <h3>{matches.length > 0 ? `${matches.length} Photos Found` : 'Waiting for scan...'}</h3>
            {matches.length > 0 && <button className="v1-btn-small" onClick={rescan}>Rescan</button>}
          </div>

          {matches.length === 0 ? (
            <div className="v1-empty">
              <span>📷</span>
              <p>Position your child's face in the camera to find their event photos</p>
            </div>
          ) : (
            <div className="v1-photo-grid">
              {matches.map(m => (
                <article key={m.id} className="v1-photo-card" onClick={() => openPurchase(m)}>
                  <div className="v1-photo-img-wrap">
                    <img src={abs(m.preview_url)} alt="Match" loading="lazy" className={purchased.has(m.id) ? '' : 'blurred'} />
                    {!purchased.has(m.id) && <div className="v1-lock-badge">🔒</div>}
                    {purchased.has(m.id) && <div className="v1-unlocked-badge">✓</div>}
                  </div>
                  <div className="v1-photo-meta">
                    <span className="v1-confidence">{Math.round(m.confidence_pct)}% match</span>
                    <span className="v1-photo-action">{purchased.has(m.id) ? 'View' : 'Unlock →'}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
      <canvas ref={canvasRef} style={{ display: 'none' }} />

      {/* Global Toast System Portal */}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast-alert ${t.type}`}>
            <span className="toast-icon">{t.type === 'success' ? '✓' : t.type === 'error' ? '✕' : 'ℹ'}</span>
            <span>{t.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════ */
/* VERSION 1 ROOT                                                     */
/* ══════════════════════════════════════════════════════════════════ */
function SplashIntro({ onComplete }: { onComplete: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onComplete, 2500);
    return () => clearTimeout(timer);
  }, [onComplete]);

  return (
    <div className="v1-splash">
      <div className="v1-splash-content">
        <div className="v1-splash-icon">📸</div>
        <h1 className="v1-splash-title">SchoolSnap AI</h1>
        <p className="v1-splash-subtitle">Parent Portal</p>
        <div className="v1-splash-loader"></div>
      </div>
    </div>
  );
}

export default function Version1App() {
  const [session, setSession] = useState<Session | null>(null);
  const [showSplash, setShowSplash] = useState(true);

  if (showSplash) return <SplashIntro onComplete={() => setShowSplash(false)} />;
  if (!session) return <LoginPage onLogin={setSession} />;
  return <ScannerPage session={session} onLogout={() => setSession(null)} />;
}
