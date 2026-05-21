import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const abs = (p: string) => (p.startsWith('http') ? p : `${API}${p}`);

type Session = { token: string; registration_number: string; parent_name: string; child_id: string; child_name: string };
type Match = { id: string; preview_url: string; confidence_pct: number; source: string };
type EventInfo = { id: string; name: string; status: string; processed: number; total: number };

function blob(c: HTMLCanvasElement): Promise<Blob> {
  return new Promise((r, e) => c.toBlob(b => (b ? r(b) : e(new Error('fail'))), 'image/jpeg', 0.92));
}

/* ── Spam / Ad banners for monetization demo ── */
const SPAM_ADS = [
  { title: '🖼️ Canvas Prints', subtitle: 'Order premium wall art from ₹499', color: '#f59e0b' },
  { title: '📦 Family Bundle', subtitle: 'Get all 10 photos — save 30%', color: '#10b981' },
  { title: '🎁 Gift a Memory', subtitle: 'Send HD photos to grandparents', color: '#ec4899' },
  { title: '📅 Annual Pass', subtitle: 'Unlimited events — ₹999/year', color: '#8b5cf6' },
];

function SpamCard({ ad }: { ad: typeof SPAM_ADS[0] }) {
  return (
    <div className="v2-spam-card" style={{ borderColor: `${ad.color}40` }}>
      <div className="v2-spam-accent" style={{ background: ad.color }} />
      <div className="v2-spam-content">
        <div className="v2-spam-title">{ad.title}</div>
        <div className="v2-spam-sub">{ad.subtitle}</div>
      </div>
      <div className="v2-spam-badge" style={{ background: `${ad.color}20`, color: ad.color }}>AD</div>
    </div>
  );
}

/* ── Secure Header (Aether style) ── */
function SecureHeader({ title, onBack }: { title: string; onBack?: () => void }) {
  return (
    <header className="secure-nav">
      <div className="nav-left">
        {onBack && <button className="back-glass-btn" onClick={onBack}><span className="arrow">←</span></button>}
        <h1>{title}</h1>
      </div>
      <div className="secure-badge"><span className="pulse-dot" />SECURE</div>
    </header>
  );
}

/* ══════════════════════════════════════════════════════════════════ */
/* ADMIN UPLOAD                                                       */
/* ══════════════════════════════════════════════════════════════════ */
function AdminUpload() {
  const [files, setFiles] = useState<File[]>([]);
  const [eventName, setEventName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState('');
  const [events, setEvents] = useState<EventInfo[]>([]);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const loadEvents = async () => {
    try { const r = await fetch(`${API}/events`); if (r.ok) setEvents(await r.json()); } catch {/* */}
  };
  useEffect(() => { void loadEvents(); const i = setInterval(loadEvents, 5000); return () => clearInterval(i); }, []);

  const upload = async (e: FormEvent) => {
    e.preventDefault();
    if (!files.length || !eventName.trim() || uploading) return;
    setUploading(true); setMsg('');
    try {
      const fd = new FormData();
      fd.append('event_name', eventName.trim());
      files.forEach(f => fd.append('files', f));
      const r = await fetch(`${API}/upload-event-images`, { method: 'POST', body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail ?? 'Upload failed');
      // Process
      const fd2 = new FormData();
      fd2.append('upload_id', d.upload_id);
      await fetch(`${API}/process-event-images`, { method: 'POST', body: fd2 });
      setMsg(`✓ ${d.total_images} photos queued for indexing`);
      setFiles([]); setEventName('');
      void loadEvents();
    } catch (x) { setMsg(x instanceof Error ? `✕ ${x.message}` : '✕ Failed'); }
    finally { setUploading(false); }
  };

  return (
    <div className="aether-layout">
      <SecureHeader title="Admin Console" onBack={() => (window.location.href = '/')} />
      <main className="shell narrow">
        <section className="glass-card enrollment-card-aether">
          <div className="grid-bg-overlay" />
          <div className="card-top">
            <div className="neon-label">EVENT MANAGEMENT</div>
            <div className="secure-badge"><div className="pulse-dot" />ADMIN</div>
          </div>
          <h2>Upload Event Photos</h2>
          <p>Drag and drop photos to index faces for parent retrieval.</p>
        </section>

        <section className="glass-card">
          <form className="stack-form" onSubmit={upload}>
            <label>
              <span className="neon-label">Event Name</span>
              <input value={eventName} onChange={e => setEventName(e.target.value)} required placeholder="e.g. Annual Day 2026" />
            </label>
            <div
              className={`dropzone-aether ${drag ? 'drag-over' : ''}`}
              onDragOver={e => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={e => { e.preventDefault(); setDrag(false); setFiles(Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'))); }}
              onClick={() => inputRef.current?.click()}
            >
              <div className="dropzone-content">
                <span className="icon">📸</span>
                <div className="neon-label">DROP ZONE</div>
                <p>{files.length > 0 ? `${files.length} files staged` : 'Drag event photos here'}</p>
              </div>
              <input ref={inputRef} type="file" multiple accept="image/*" onChange={e => setFiles(Array.from(e.target.files ?? []))} className="hidden" style={{ display: 'none' }} />
            </div>
            <button type="submit" disabled={uploading || !files.length || !eventName.trim()} className="neon-btn">
              {uploading ? 'UPLOADING...' : 'UPLOAD & INDEX'}
            </button>
            {msg && <div className={`feedback ${msg.startsWith('✓') ? 'status-green' : 'status-red'}`}>{msg}</div>}
          </form>
        </section>

        {events.length > 0 && (
          <section className="glass-card">
            <div className="neon-label">INDEXED EVENTS</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
              {events.map(ev => (
                <div key={ev.id} className="v2-event-row">
                  <div><strong>{ev.name}</strong></div>
                  <div className="v2-event-status">
                    <span className={`v2-status-pill ${ev.status}`}>{ev.status}</span>
                    <span>{ev.processed}/{ev.total}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════ */
/* PARENT ACCESS (Investor version — with spam)                       */
/* ══════════════════════════════════════════════════════════════════ */
function ParentAccessV2() {
  const [reg, setReg] = useState(''); const [dob, setDob] = useState('');
  const [session, setSession] = useState<Session | null>(null);
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<'idle' | 'scanning' | 'hologram' | 'found' | 'none'>('idle');
  const [msg, setMsg] = useState(''); const [matches, setMatches] = useState<Match[]>([]);
  const [camErr, setCamErr] = useState('');
  const [selected, setSelected] = useState<Match | null>(null);
  const [purchased, setPurchased] = useState<Set<string>>(new Set());
  const [payStep, setPayStep] = useState<'pay' | 'code' | 'done'>('pay');
  const [email, setEmail] = useState(''); const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState(''); const [otpErr, setOtpErr] = useState('');

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
  const scanningRef = useRef(false);

  const stopCam = useCallback(() => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
  }, []);

  const doScan = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current || !session || scanningRef.current) return;
    scanningRef.current = true;
    addLog('Querying quantum optic frames...', 'info');
    try {
      const c = canvasRef.current, v = videoRef.current;
      if (v.readyState < 2) return;
      c.width = v.videoWidth || 720; c.height = v.videoHeight || 720;
      const ctx = c.getContext('2d'); if (!ctx) return;
      ctx.drawImage(v, 0, 0, c.width, c.height);
      const b = await blob(c);
      const fd = new FormData();
      fd.append('token', session.token); fd.append('file', b, 'scan.jpg');
      
      addLog('Transmitting biometric vector to Aether Secure Index...', 'info');
      const r = await fetch(`${API}/parent/scan-and-match`, { method: 'POST', body: fd });
      if (!r.ok) {
        addLog('Biometric server returned a cluster error.', 'error');
        return;
      }
      const d = await r.json();
      if (d.status === 'green' && d.matches?.length > 0) {
        if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
        addLog('BIOMETRIC RETRIEVAL MATCH CONFIRMED', 'success');
        addLog('Computing face depth vectors...', 'info');
        showToast('Authorized biometric sequence recognized!', 'success');
        
        setStatus('hologram');
        setTimeout(() => {
          setStatus('found');
          setMsg(d.message);
          setMatches(d.matches);
          addLog(`Asset catalog loaded: ${d.matches.length} elements decryption verified.`, 'success');
          showToast(`Unlocked ${d.matches.length} matches!`, 'success');
        }, 1200);
      } else {
        setStatus('scanning');
        setMsg(d.message || 'Scanning...');
        addLog(`Match cycle completed. Result: ${d.message || 'Biometric key mismatch'}`, 'warn');
      }
    } catch {
      addLog('Aether biometric network frame dropped.', 'error');
    }
    finally { scanningRef.current = false; }
  }, [session, addLog, showToast]);

  const startCam = useCallback(async () => {
    if (!videoRef.current) return; setCamErr('');
    addLog('Initializing quantum optic arrays...', 'info');
    try {
      stopCam();
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 480 }, height: { ideal: 480 } } });
      streamRef.current = s; videoRef.current.srcObject = s; await videoRef.current.play();
      setStatus('scanning'); setMsg('Scanning... Position face.');
      addLog('Optic feed lock established. Model is tracking vectors.', 'success');
      showToast('Aether optical engine online', 'info');
      setTimeout(() => { intervalRef.current = setInterval(() => void doScan(), 3500); void doScan(); }, 1500);
    } catch { 
      setCamErr('Camera access denied. Activating emulation node...'); 
      setStatus('scanning'); setMsg('Emulating virtual scanner...');
      addLog('Optic capture arrays bypassed. Activating simulation node...', 'warn');
      showToast('Optics offline. Emulating scan...', 'info');
      
      // MOCK MATCH FOR VIDEO
      setTimeout(() => {
        addLog('Decrypting mock biometric vectors...', 'info');
        setStatus('hologram');
        setTimeout(() => {
          setStatus('found'); setMsg('Matches found successfully!'); 
          setMatches([
            { id: 'mock1', preview_url: '/images/previews/evt101.jpg', confidence_pct: 95.4, source: 'evt101.jpg' },
            { id: 'mock2', preview_url: '/images/previews/evt102.jpg', confidence_pct: 88.2, source: 'evt102.jpg' }
          ]);
          setCamErr('');
          addLog('Aether mock authorization successful!', 'success');
          showToast('Mock biometric authorization complete!', 'success');
        }, 1200);
      }, 3000);
    }
  }, [stopCam, doScan, addLog, showToast]);

  useEffect(() => { if (session) void startCam(); return () => stopCam(); }, [session, startCam, stopCam]);

  const login = async (e: FormEvent) => {
    e.preventDefault(); setErr(''); setBusy(true);
    const fd = new FormData(); fd.append('registration_number', reg.trim()); fd.append('dob', dob.trim());
    try {
      const r = await fetch(`${API}/parent-login`, { method: 'POST', body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail);
      setSession(d);
    }
    catch (x) { setErr(x instanceof Error ? x.message : 'Failed'); }
    finally { setBusy(false); }
  };

  const logout = () => { stopCam(); setSession(null); setMatches([]); setStatus('idle'); setSelected(null); };
  const rescan = () => {
    addLog('Resetting token caches. Preparing array scan...', 'warn');
    showToast('Restarting optic stream...', 'info');
    setMatches([]); setStatus('scanning');
    if (!intervalRef.current) intervalRef.current = setInterval(() => void doScan(), 3500);
  };

  /* Login Screen */
  if (!session) return (
    <div className="aether-layout">
      <SecureHeader title="Parent Portal" onBack={() => (window.location.href = '/')} />
      <main className="shell narrow centered-shell">
        <div className="hero-fingerprint-wrap">
          <div className="hero-glow" />
          <div className="fingerprint-glass">
            <div className="fingerprint-icon">🔍</div>
          </div>
        </div>
        <section className="glass-card login-card-aether">
          <div className="card-header">
            <h2>Welcome Back</h2>
            <p>Authorize access with your student credentials</p>
          </div>
          <form className="stack-form" onSubmit={login}>
            <label>
              <span className="neon-label">Registration No.</span>
              <input value={reg} onChange={e => setReg(e.target.value)} required placeholder="REG1001" />
            </label>
            <label>
              <span className="neon-label">Date of Birth</span>
              <input type="date" value={dob} onChange={e => setDob(e.target.value)} required />
            </label>
            {err && <p style={{ color: '#ef4444', fontSize: '0.88rem' }}>{err}</p>}
            <button type="submit" disabled={busy} className="neon-btn">
              {busy ? 'Authenticating...' : 'Continue to Scan'}
              <span className="arrow-icon">→</span>
            </button>
          </form>
        </section>
        <section className="demo-credentials-glass">
          <div className="neon-label">DEMO ACCESS</div>
          <p>REG1001 / 2014-05-12</p>
        </section>
      </main>
    </div>
  );


  const handleSkipScan = () => {
    stopCam();
    addLog('MANUAL PORTAL BYPASS INITIATED', 'warn');
    addLog('Compiling emergency decrypt key...', 'info');
    showToast('Secure skip triggered! Decoding meshes...', 'info');
    setStatus('hologram');
    
    setTimeout(() => addLog('Quantum grid initialized.', 'info'), 300);
    setTimeout(() => addLog('Matching depth profile (812 face points)...', 'info'), 600);
    setTimeout(() => addLog('Retrieving secure matching elements...', 'info'), 900);

    setTimeout(() => {
      setStatus('found');
      setMsg('Demo Mode: Face Scan Bypassed');
      addLog('Decryption authorized: 4 high-res fragments isolated.', 'success');
      showToast('Public event memories decoded!', 'success');
      setMatches([
        { id: 'demo1', preview_url: 'https://images.unsplash.com/photo-1544717305-2782549b5136?q=80&w=600&auto=format&fit=crop', confidence_pct: 97.8, source: 'annual_sports_012.jpg' },
        { id: 'demo2', preview_url: 'https://images.unsplash.com/photo-1503676260728-1c00da094a0b?q=80&w=600&auto=format&fit=crop', confidence_pct: 91.5, source: 'classroom_science_04.jpg' },
        { id: 'demo3', preview_url: 'https://images.unsplash.com/photo-1588072432836-e10032774350?q=80&w=600&auto=format&fit=crop', confidence_pct: 88.3, source: 'school_assembly_09.jpg' },
        { id: 'demo4', preview_url: 'https://images.unsplash.com/photo-1516627145497-ae6968895b74?q=80&w=600&auto=format&fit=crop', confidence_pct: 84.1, source: 'playground_recess_02.jpg' }
      ]);
    }, 1200);
  };

  // Canvas animation for Scanning Overlay (V2 Aether Cyan Style)
  useEffect(() => {
    if (status !== 'scanning' || !videoRef.current || !overlayCanvasRef.current) return;
    const canvas = overlayCanvasRef.current;
    const video = videoRef.current;
    let active = true;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dots: { x: number; y: number; vx: number; vy: number }[] = [];
    for (let i = 0; i < 20; i++) {
      dots.push({
        x: 0.35 + Math.random() * 0.3,
        y: 0.3 + Math.random() * 0.4,
        vx: (Math.random() - 0.5) * 0.005,
        vy: (Math.random() - 0.5) * 0.005,
      });
    }

    let angle = 0;

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

      // Oval Face Guide (Aether Cyan)
      ctx.strokeStyle = 'rgba(0, 229, 255, 0.35)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 6]);
      ctx.beginPath();
      ctx.ellipse(w / 2, h / 2, w * 0.28, h * 0.36, 0, 0, 2 * Math.PI);
      ctx.stroke();
      ctx.setLineDash([]);

      // Dynamic Mesh
      ctx.fillStyle = 'rgba(0, 229, 255, 0.85)';
      ctx.strokeStyle = 'rgba(0, 229, 255, 0.2)';
      ctx.lineWidth = 1;
      dots.forEach(d => {
        d.x += d.vx;
        d.y += d.vy;
        if (d.x < 0.25 || d.x > 0.75) d.vx *= -1;
        if (d.y < 0.2 || d.y > 0.8) d.vy *= -1;

        ctx.beginPath();
        ctx.arc(d.x * w, d.y * h, 2.5, 0, 2 * Math.PI);
        ctx.fill();
      });

      // Links
      for (let i = 0; i < dots.length; i++) {
        for (let j = i + 1; j < dots.length; j++) {
          const dx = (dots[i].x - dots[j].x) * w;
          const dy = (dots[i].y - dots[j].y) * h;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < w * 0.16) {
            ctx.beginPath();
            ctx.moveTo(dots[i].x * w, dots[i].y * h);
            ctx.lineTo(dots[j].x * w, dots[j].y * h);
            ctx.stroke();
          }
        }
      }

      // Corner Brackets
      const pad = 24;
      const len = 16;
      ctx.strokeStyle = '#00E5FF';
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

      // Telemetry ring
      angle += 0.02;
      ctx.strokeStyle = 'rgba(0, 229, 255, 0.45)';
      ctx.beginPath();
      ctx.arc(w / 2, h / 2, w * 0.14, angle, angle + 1.2);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(w / 2, h / 2, w * 0.14, angle + Math.PI, angle + Math.PI + 1.2);
      ctx.stroke();

      // Crosshairs
      ctx.strokeStyle = 'rgba(0, 229, 255, 0.25)';
      ctx.beginPath();
      ctx.moveTo(w / 2 - 12, h / 2); ctx.lineTo(w / 2 + 12, h / 2);
      ctx.moveTo(w / 2, h / 2 - 12); ctx.lineTo(w / 2, h / 2 + 12);
      ctx.stroke();

      // Digital labels
      ctx.fillStyle = '#00E5FF';
      ctx.font = '8px Courier New, monospace';
      ctx.fillText('FACIAL_SCAN_AETHER_V2', pad, pad - 6);
      ctx.fillText('SECURE_CLUSTER: ACTIVE', w - pad - 120, pad - 6);
      ctx.fillText(`ROT_ANGLE: ${(angle * 180 / Math.PI % 360).toFixed(0)}deg`, pad, h - pad + 12);
      ctx.fillText('ALGORITHM: FAISS_IVF', w - pad - 120, h - pad + 12);

      requestAnimationFrame(render);
    };

    render();
    return () => { active = false; };
  }, [status]);

  // Canvas animation for 1.2s Hologram Scan on Bypass (Cyan V2 Aether)
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

      ctx.strokeStyle = 'rgba(0, 229, 255, 0.45)';
      ctx.fillStyle = '#00E5FF';
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

      ctx.strokeStyle = 'rgba(0, 229, 255, 0.25)';
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
    addLog(`Accessing asset element target: ${m.id}`, 'info');
    setSelected(m); setPayStep(purchased.has(m.id) ? 'done' : 'pay');
    setEmail(''); setPhone(''); setOtp(''); setOtpErr('');
  };
  const closePurchase = () => {
    addLog('Returning to search HUD layout...', 'info');
    setSelected(null);
  };
  const submitPay = (e: FormEvent) => {
    e.preventDefault();
    addLog(`INITIALIZED SECURE ROUTE CHECKOUT FOR ${email || 'guest'}`, 'info');
    addLog('Sending transaction credentials to gateway node...', 'info');
    showToast('Contacting payment node...', 'info');
    setTimeout(() => {
      setPayStep('code');
      addLog('Aether Shield: Access authorized. Enter verification link.', 'warn');
      addLog('One-Time-Key dispatched successfully.', 'success');
      showToast('OTP link sent to device!', 'success');
    }, 800);
  };
  const verifyCode = (e: FormEvent) => {
    e.preventDefault();
    addLog(`VERIFYING SECURITY PIN FOR REF: ATH-847293`, 'info');
    if (otp.trim() === '847293') {
      addLog('PIN VERIFICATION PROTOCOL: MATCH CONFIRMED.', 'success');
      showToast('Quantum authorization key authenticated!', 'success');
      setPayStep('done'); setOtpErr('');
      if (selected) {
        setPurchased(p => new Set([...p, selected.id]));
        addLog(`Granted permanent HD access certificate for asset ${selected.id}`, 'success');
      }
    } else {
      addLog('SECURITY FAILURE: VERIFICATION MISMATCH.', 'error');
      showToast('Invalid quantum pin. Try again.', 'error');
      setOtpErr('Invalid code');
    }
  };
  const download = () => {
    if (!selected) return;
    addLog(`Initiating download for source: ${selected.source}`, 'info');
    showToast('Downloading premium photo...', 'success');
    const a = document.createElement('a'); a.href = abs(selected.preview_url); a.download = `SchoolSnap_HD_${selected.id}.jpg`; a.target = '_blank';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  };

  /* Purchase */
  if (selected) return (
    <div className="aether-layout">
      <SecureHeader title="Photo Intelligence" onBack={closePurchase} />
      <main className="shell narrow">
        <div className="glass-card purchase-card-aether">
          <div className={`purchase-preview-glass ${payStep === 'done' ? 'unlocked' : ''}`}>
            <img src={abs(selected.preview_url)} alt="Photo" loading="lazy" />
            {payStep !== 'done' && <div className="watermark-text-aether">SECURE PREVIEW</div>}
            <div className="scan-line-horizontal" />
          </div>
          <div className="purchase-details">
            <div className="neon-label">STATUS: {purchased.has(selected.id) ? 'AUTHORIZED' : 'LOCKED'}</div>
            <div className="purchase-steps-aether">
              <div className={`p-step ${payStep === 'pay' ? 'active' : 'done'}`}>PAY</div><div className="p-divider" />
              <div className={`p-step ${payStep === 'code' ? 'active' : payStep === 'done' ? 'done' : ''}`}>VERIFY</div><div className="p-divider" />
              <div className={`p-step ${payStep === 'done' ? 'active' : ''}`}>ACCESS</div>
            </div>

            {/* HIGH-TECH 3D ROTATING CREDIT CARD / OTP SECURE CODE */}
            {payStep !== 'done' && (
              <div className="payment-flip-container v2-checkout-flip">
                <div className={`payment-flip-inner ${payStep === 'code' ? 'flipped' : ''}`}>
                  
                  {/* FRONT SIDE (Aether Secure Credit Card) */}
                  <div className="payment-card-front v2-pay-card">
                    <div className="payment-card-glow" />
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div className="payment-card-chip" />
                      <span className="payment-card-logo">Aether Secure Pay</span>
                    </div>
                    <div>
                      <div style={{ fontFamily: 'monospace', fontSize: '1rem', letterSpacing: '0.15em', marginBottom: '0.35rem', color: '#fff' }}>
                        •••• •••• •••• 9214
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', opacity: 0.8 }}>
                        <span>HOLDER: AETHER PREMIUM PARENT</span>
                        <span>EXP: 11/30</span>
                      </div>
                    </div>
                  </div>

                  {/* BACK SIDE (Aether Secure OTP Access Pad) */}
                  <div className="payment-card-back v2-pay-card">
                    <div className="payment-card-glow" />
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.7rem', fontWeight: 'bold', color: 'var(--v2-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>OTP QUANTUM ACCESS</span>
                      <span className="payment-card-logo">AETHER SHIELD</span>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.6)', padding: '0.5rem', borderRadius: '6px', border: '1px solid rgba(0, 229, 255, 0.15)', textAlign: 'center' }}>
                      <span style={{ fontSize: '0.8rem', opacity: 0.9, fontFamily: 'monospace', color: 'var(--v2-primary)', letterSpacing: '0.05em' }}>QUANTUM PAD ACTIVE</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.65rem', opacity: 0.6 }}>Reference Code: ATH-847293</span>
                      <span style={{ color: 'var(--v2-success)', fontWeight: 'bold', fontSize: '0.7rem' }}>🔐 SECURE LINK</span>
                    </div>
                  </div>

                </div>
              </div>
            )}

            {payStep === 'pay' && (
              <form className="stack-form" onSubmit={submitPay}>
                <div className="price-badge-aether">PREMIUM RELEASE: ₹149</div>
                <label><span className="neon-label">Email</span><input type="email" value={email} onChange={e => setEmail(e.target.value)} required /></label>
                <label><span className="neon-label">Phone</span><input type="tel" value={phone} onChange={e => setPhone(e.target.value)} required /></label>
                <button type="submit" className="neon-btn">Authorize Payment</button>
              </form>
            )}
            {payStep === 'code' && (
              <form className="stack-form" onSubmit={verifyCode}>
                <div className="status-msg-aether">CODE TRANSMITTED TO {phone || email}</div>
                <label><span className="neon-label">Entry Code</span><input type="text" className="code-input-aether" value={otp} onChange={e => setOtp(e.target.value)} required maxLength={6} placeholder="000000" /></label>
                {otpErr && <p className="error-text-aether">✕ {otpErr}</p>}
                <button type="submit" className="neon-btn">Verify Access</button>
                <p className="hint-text-aether">Use: 847293</p>
              </form>
            )}
            {payStep === 'done' && (
              <div className="success-action-aether">
                <button className="neon-btn" onClick={download}>Download High-Res</button>
                <button className="ghost-btn-aether" onClick={closePurchase}>Find More Photos</button>
              </div>
            )}

            {/* Rolling Logs inside Aether Checkout Card */}
            <div className="terminal-log-console" ref={logConsoleRef} style={{ marginTop: '1.5rem', width: 'auto' }}>
              {logs.map(log => (
                <div key={log.id} className={`terminal-line ${log.type}`}>
                  [{log.time}] {log.text}
                </div>
              ))}
            </div>
          </div>
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

  /* Scanner + Results with Spam */
  return (
    <div className="aether-layout">
      <SecureHeader title="Biometric Scanner" onBack={logout} />
      <main className="shell">
        <div className="scanner-grid-aether">
          <section className="glass-card scanner-hud-aether">
            <div className="hud-header">
              <div className="neon-label">BIOMETRIC_HUD</div>
              <div className="secure-badge"><div className="pulse-dot" />ACTIVE</div>
            </div>
            <div className="camera-viewport-aether">
              <div className="hud-frame" />
              <video ref={videoRef} playsInline muted className="camera-stream" />
              {status === 'scanning' && <canvas ref={overlayCanvasRef} className="v1-cam-overlay" />}
              {status === 'hologram' && (
                <div className="holographic-bypass-container">
                  <div className="holographic-title">HOLOGRAPHIC VECTOR SCAN</div>
                  <canvas ref={holoCanvasRef} className="holographic-canvas" />
                  <div className="holographic-terminal">
                    <div style={{ color: '#00E5FF' }}>⚡ BYPASS ENGINE RUNNING</div>
                    <div>- QUANTUM COHERENCE INDEXING...</div>
                    <div>- SOLVING DEEP VECTOR LATTICE...</div>
                  </div>
                </div>
              )}
              {status === 'scanning' && <div className="hud-scan-line" />}
              {camErr && <div className="hud-error-overlay"><span>UNABLE TO ACCESS OPTICS</span><p>{camErr}</p></div>}
            </div>
            
            {status === 'scanning' && (
              <button 
                type="button" 
                className="neon-btn" 
                onClick={handleSkipScan}
                style={{
                  width: 'calc(100% - 2rem)',
                  margin: '0.5rem 1rem 1rem',
                  border: '1px dashed var(--v2-primary)',
                  background: 'rgba(0, 229, 255, 0.08)',
                  color: 'var(--v2-primary)',
                  fontWeight: 600,
                  fontSize: '0.9rem',
                  letterSpacing: '0.05em'
                }}
              >
                ⚡ BYPASS PROTOCOL: DEMO SCAN
              </button>
            )}

            {/* Scrolling Logs inside Scanner HUD */}
            <div className="terminal-log-console" ref={logConsoleRef} style={{ width: 'calc(100% - 2rem)', margin: '0.5rem 1rem 1rem' }}>
              {logs.length === 0 ? (
                <div className="terminal-line info">[SYSTEM] Standby. Optical engines loaded.</div>
              ) : (
                logs.map(log => (
                  <div key={log.id} className={`terminal-line ${log.type}`}>
                    [{log.time}] {log.text}
                  </div>
                ))
              )}
            </div>

            <div className="hud-footer">
              <div className="hud-message">{msg}</div>
              <div className="hud-stats">
                <div className="stat-bit">FPS: 24.0</div>
                <div className="stat-bit">LATENCY: 142ms</div>
                <div className="stat-bit">STORE: FAISS_V1</div>
              </div>
            </div>
          </section>

          <section className="results-panel-aether">
            <div className="panel-header">
              <div className="neon-label">DETECTED_FRAGMENTS ({matches.length})</div>
              <button className="neon-btn small" onClick={rescan} style={{ width: 'auto', padding: '0.5rem 1rem' }}>RE-SCAN</button>
            </div>
            {matches.length === 0 ? (
              <div className="glass-card empty-panel-aether"><div className="search-icon-anim">🔍</div><p>Waiting for biometric match...</p></div>
            ) : (
              <div className="results-scroll-aether">
                {matches.map((m, i) => (
                  <div key={m.id}>
                    <article className="glass-card match-card-aether" onClick={() => openPurchase(m)}>
                      <div className="match-img-wrap">
                        <img src={abs(m.preview_url)} alt="Detection" loading="lazy" />
                        {purchased.has(m.id) && <div className="unlocked-tag">AUTHORIZED</div>}
                      </div>
                      <div className="match-meta">
                        <div className="neon-label small">MATCH_SIG: 10/10</div>
                        <span className="confidence-aether">CONFIDENCE: {Math.round(m.confidence_pct)}%</span>
                        <div className="source-link-aether">RETRIEVE ACCESS →</div>
                      </div>
                    </article>
                    {/* Inject spam after every 2nd photo */}
                    {(i + 1) % 2 === 0 && i < matches.length - 1 && <SpamCard ad={SPAM_ADS[((i / 2) | 0) % SPAM_ADS.length]} />}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
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
/* HOME PAGE (Investor version — shows both portals)                  */
/* ══════════════════════════════════════════════════════════════════ */
function HomePageV2() {
  return (
    <div className="aether-layout">
      <SecureHeader title="Aether Security" />
      <main className="shell">
        <section className="glass-card hero-aether">
          <div className="neon-label">SYSTEM STATUS: ACTIVE</div>
          <h1>SchoolSnap AI</h1>
          <p>Instant biometric photo retrieval for premium school events.<br />Powered by Aether Security Protocols.</p>
        </section>
        <section className="split-grid">
          <a href="/admin" className="portal-link-aether">
            <article className="glass-card portal-card">
              <div className="card-top"><span className="icon">🏫</span><div className="neon-label">ADMIN</div></div>
              <h2>Upload Photos</h2>
              <p>Bulk upload and index event photos for face recognition.</p>
              <div className="portal-arrow-aether">ENTER PORTAL →</div>
            </article>
          </a>
          <a href="/parent" className="portal-link-aether">
            <article className="glass-card portal-card">
              <div className="card-top"><span className="icon">🛡️</span><div className="neon-label">PUBLIC</div></div>
              <h2>Parent Access</h2>
              <p>Scan face to instantly retrieve and unlock event memories.</p>
              <div className="portal-arrow-aether">ACCESS SYSTEM →</div>
            </article>
          </a>
        </section>
      </main>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════ */
/* VERSION 2 ROUTER                                                   */
/* ══════════════════════════════════════════════════════════════════ */
export default function Version2App() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => { const h = () => setPath(window.location.pathname); window.addEventListener('popstate', h); return () => window.removeEventListener('popstate', h); }, []);

  if (path === '/admin') return <AdminUpload />;
  if (path === '/parent') return <ParentAccessV2 />;
  return <HomePageV2 />;
}
