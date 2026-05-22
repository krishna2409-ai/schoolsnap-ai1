import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import FaceMeshOverlay from './FaceMeshOverlay';
import { useFaceTracking } from '../hooks/useFaceTracking';

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
  const [status, setStatus] = useState<'idle' | 'scanning' | 'found' | 'none'>('idle');
  const [msg, setMsg] = useState(''); const [matches, setMatches] = useState<Match[]>([]);
  const [camErr, setCamErr] = useState('');
  const [selected, setSelected] = useState<Match | null>(null);
  const [purchased, setPurchased] = useState<Set<string>>(new Set());
  const [payStep, setPayStep] = useState<'pay' | 'code' | 'done'>('pay');
  const [email, setEmail] = useState(''); const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState(''); const [otpErr, setOtpErr] = useState('');

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const scanningRef = useRef(false);
  const cameraRunRef = useRef(0);
  const trackedFace = useFaceTracking(videoRef, status === 'scanning', API);

  const stopCam = useCallback(() => {
    cameraRunRef.current += 1;
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
  }, []);

  const doScan = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current || !session || scanningRef.current) return;
    scanningRef.current = true;
    try {
      const c = canvasRef.current, v = videoRef.current;
      if (v.readyState < 2) return;
      c.width = v.videoWidth || 720; c.height = v.videoHeight || 720;
      const ctx = c.getContext('2d'); if (!ctx) return;
      ctx.drawImage(v, 0, 0, c.width, c.height);
      const b = await blob(c);
      const fd = new FormData();
      fd.append('token', session.token); fd.append('file', b, 'scan.jpg');
      const r = await fetch(`${API}/parent/scan-and-match`, { method: 'POST', body: fd });
      if (!r.ok) return;
      const d = await r.json();
      if (d.status === 'green' && d.matches?.length > 0) {
        if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
        setStatus('found'); setMsg(d.message); setMatches(d.matches);
      } else { setStatus('scanning'); setMsg(d.message || 'Scanning...'); }
    } catch {/* keep scanning */}
    finally { scanningRef.current = false; }
  }, [session]);

  const startCam = useCallback(async () => {
    if (!videoRef.current) return; setCamErr('');
    try {
      stopCam();
      const runId = ++cameraRunRef.current;
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 480 }, height: { ideal: 480 } } });
      if (runId !== cameraRunRef.current || !videoRef.current) {
        s.getTracks().forEach(t => t.stop());
        return;
      }
      streamRef.current = s; videoRef.current.srcObject = s; await videoRef.current.play();
      setStatus('scanning'); setMsg('Scanning... Position face.');
      setTimeout(() => {
        if (runId !== cameraRunRef.current) return;
        intervalRef.current = setInterval(() => void doScan(), 3500);
        void doScan();
      }, 1500);
    } catch {
      if (!streamRef.current) setCamErr('Camera access denied.');
    }
  }, [stopCam, doScan]);

  useEffect(() => { if (session) void startCam(); return () => stopCam(); }, [session, startCam, stopCam]);

  useEffect(() => {
    if (videoRef.current && streamRef.current && !videoRef.current.srcObject) {
      videoRef.current.srcObject = streamRef.current;
      void videoRef.current.play().catch(() => {});
    }
  }, [selected]);

  const login = async (e: FormEvent) => {
    e.preventDefault(); setErr(''); setBusy(true);
    const fd = new FormData(); fd.append('registration_number', reg.trim()); fd.append('dob', dob.trim());
    try { const r = await fetch(`${API}/parent-login`, { method: 'POST', body: fd }); const d = await r.json(); if (!r.ok) throw new Error(d.detail); setSession(d); }
    catch (x) { setErr(x instanceof Error ? x.message : 'Failed'); }
    finally { setBusy(false); }
  };

  const logout = () => { stopCam(); setSession(null); setMatches([]); setStatus('idle'); setSelected(null); };
  const rescan = () => {
    setMatches([]);
    void startCam();
  };

  const openPurchase = (m: Match) => { setSelected(m); setPayStep(purchased.has(m.id) ? 'done' : 'pay'); };
  const closePurchase = () => { setSelected(null); };
  const submitPay = (e: FormEvent) => { e.preventDefault(); setPayStep('code'); };
  const verifyCode = (e: FormEvent) => {
    e.preventDefault();
    if (otp.trim() === '847293') { setPayStep('done'); setOtpErr(''); if (selected) setPurchased(p => new Set([...p, selected.id])); }
    else setOtpErr('Invalid code');
  };
  const download = () => {
    if (!selected) return;
    const a = document.createElement('a'); a.href = abs(selected.preview_url); a.download = `SchoolSnap_HD_${selected.id}.jpg`; a.target = '_blank';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  };

  /* Login Screen */
  if (!session) return (
    <div className="aether-layout">
      <SecureHeader title="Parent Portal" onBack={() => (window.location.href = '/')} />
      <main className="shell narrow centered-shell">
        <div className="hero-fingerprint-wrap"><div className="hero-glow" /><div className="fingerprint-glass"><div className="fingerprint-icon">🔍</div></div></div>
        <section className="glass-card login-card-aether">
          <div className="card-header"><h2>Welcome Back</h2><p>Authorize access with your student credentials</p></div>
          <form className="stack-form" onSubmit={login}>
            <label><span className="neon-label">Registration No.</span><input value={reg} onChange={e => setReg(e.target.value)} required placeholder="REG1001" /></label>
            <label><span className="neon-label">Date of Birth</span><input type="date" value={dob} onChange={e => setDob(e.target.value)} required /></label>
            {err && <p style={{ color: '#ef4444', fontSize: '0.88rem' }}>{err}</p>}
            <button type="submit" disabled={busy} className="neon-btn">{busy ? 'Authenticating...' : 'Continue to Scan'}<span className="arrow-icon">→</span></button>
          </form>
        </section>
        <section className="demo-credentials-glass"><div className="neon-label">DEMO ACCESS</div><p>REG1001 / 2014-05-12</p></section>
      </main>
    </div>
  );

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
          </div>
        </div>
      </main>
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
              <FaceMeshOverlay active={status === 'scanning'} face={trackedFace} />
              {status === 'scanning' && <div className="hud-scan-line" />}
              {camErr && <div className="hud-error-overlay"><span>UNABLE TO ACCESS OPTICS</span><p>{camErr}</p></div>}
            </div>
            <div className="hud-footer">
              <div className="hud-message">{msg}</div>
              <div className="hud-stats"><div className="stat-bit">FPS: 24.0</div><div className="stat-bit">LATENCY: 142ms</div><div className="stat-bit">STORE: FAISS_V1</div></div>
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
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════ */
/* HOME PAGE (Investor version — shows both portals)                  */
/* ══════════════════════════════════════════════════════════════════ */
function HomePageV2() {
  const navigate = (to: string) => {
    // Retain current subpath prefix (/investor or /v2) if present
    const prefix = window.location.pathname.match(/^\/(investor|v2)/)?.[0] ?? '';
    const targetPath = `${prefix}${to}`;
    window.history.pushState({}, '', targetPath);
    // Dispatch a popstate event so the parent router updates its path state
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

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
          <button 
            onClick={() => navigate('/admin')} 
            className="portal-link-aether-btn"
            style={{ background: 'none', border: 'none', padding: 0, textAlign: 'left', cursor: 'pointer', width: '100%' }}
          >
            <article className="glass-card portal-card">
              <div className="card-top"><span className="icon">🏫</span><div className="neon-label">ADMIN</div></div>
              <h2>Upload Photos</h2>
              <p>Bulk upload and index event photos for face recognition.</p>
              <div className="portal-arrow-aether">ENTER PORTAL →</div>
            </article>
          </button>
          <button 
            onClick={() => navigate('/parent')} 
            className="portal-link-aether-btn"
            style={{ background: 'none', border: 'none', padding: 0, textAlign: 'left', cursor: 'pointer', width: '100%' }}
          >
            <article className="glass-card portal-card">
              <div className="card-top"><span className="icon">🛡️</span><div className="neon-label">PUBLIC</div></div>
              <h2>Parent Access</h2>
              <p>Scan face to instantly retrieve and unlock event memories.</p>
              <div className="portal-arrow-aether">ACCESS SYSTEM →</div>
            </article>
          </button>
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
  
  useEffect(() => {
    const handlePopState = () => setPath(window.location.pathname);
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Normalize path to strip subpath prefixes (/investor or /v2)
  const normalizedPath = path.replace(/^\/(investor|v2)/, '');

  if (normalizedPath === '/admin') return <AdminUpload />;
  if (normalizedPath === '/parent') return <ParentAccessV2 />;
  return <HomePageV2 />;
}
