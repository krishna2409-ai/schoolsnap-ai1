import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const abs = (p: string) => (p.startsWith('http') ? p : `${API}${p}`);

type Session = { token: string; registration_number: string; parent_name: string; child_id: string; child_name: string };
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
  const [status, setStatus] = useState<'idle' | 'scanning' | 'found' | 'none'>('idle');
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

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
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
      } else {
        setStatus('scanning'); setMsg(d.message || 'Scanning...');
      }
    } catch { /* keep scanning */ }
    finally { busyRef.current = false; }
  }, [session]);

  const startCam = useCallback(async () => {
    if (!videoRef.current) return;
    setCamErr('');
    try {
      stopCam();
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 480 }, height: { ideal: 480 } } });
      streamRef.current = s; videoRef.current.srcObject = s; await videoRef.current.play();
      setStatus('scanning'); setMsg('Position face in frame...');
      setTimeout(() => {
        intervalRef.current = setInterval(() => void doScan(), 3500);
        void doScan();
      }, 1500);
    } catch { 
      setCamErr('Simulating virtual scan for demo...');
      setStatus('scanning'); setMsg('Scanning virtual face...');
      // MOCK MATCH FOR VIDEO
      setTimeout(() => {
        setStatus('found'); setMsg('Matches found successfully!'); 
        setMatches([
          { id: 'mock1', preview_url: '/images/previews/evt101.jpg', confidence_pct: 95.4, source: 'evt101.jpg' },
          { id: 'mock2', preview_url: '/images/previews/evt102.jpg', confidence_pct: 88.2, source: 'evt102.jpg' }
        ]);
        setCamErr('');
      }, 3000);
    }
  }, [stopCam, doScan]);

  useEffect(() => { void startCam(); return () => stopCam(); }, [startCam, stopCam]);

  const rescan = () => {
    setMatches([]); setStatus('scanning'); setMsg('Rescanning...');
    if (!intervalRef.current) { intervalRef.current = setInterval(() => void doScan(), 3500); }
  };

  const handleSkipScan = () => {
    stopCam();
    setStatus('found');
    setMsg('Demo Mode: Face Scan Bypassed');
    setMatches([
      { id: 'demo1', preview_url: 'https://images.unsplash.com/photo-1544717305-2782549b5136?q=80&w=600&auto=format&fit=crop', confidence_pct: 97.8, source: 'annual_sports_012.jpg' },
      { id: 'demo2', preview_url: 'https://images.unsplash.com/photo-1503676260728-1c00da094a0b?q=80&w=600&auto=format&fit=crop', confidence_pct: 91.5, source: 'classroom_science_04.jpg' },
      { id: 'demo3', preview_url: 'https://images.unsplash.com/photo-1588072432836-e10032774350?q=80&w=600&auto=format&fit=crop', confidence_pct: 88.3, source: 'school_assembly_09.jpg' },
      { id: 'demo4', preview_url: 'https://images.unsplash.com/photo-1516627145497-ae6968895b74?q=80&w=600&auto=format&fit=crop', confidence_pct: 84.1, source: 'playground_recess_02.jpg' }
    ]);
  };

  /* ── Purchase flow ── */
  const openPurchase = (m: Match) => {
    setSelected(m); setPayStep(purchased.has(m.id) ? 'done' : 'info');
    setEmail(''); setPhone(''); setOtp(''); setOtpErr('');
  };
  const closePurchase = () => { setSelected(null); setPayStep('info'); };

  const submitPayment = (e: FormEvent) => { e.preventDefault(); setPayStep('otp'); };
  const verifyOtp = (e: FormEvent) => {
    e.preventDefault();
    if (otp.trim() === '847293') {
      setPayStep('done'); setOtpErr('');
      if (selected) setPurchased(prev => new Set([...prev, selected.id]));
    } else { setOtpErr('Invalid code'); }
  };
  const downloadPhoto = () => {
    if (!selected) return;
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
