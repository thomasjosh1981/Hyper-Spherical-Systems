/**
 * Project Tesseract v3.3 - Center-Out Animated Pipeline
 * Spiral starts DEAD CENTER and grows outward. Tail lands on outer edge.
 */

// ==========================================
// 1. SHORT DEMO PROMPTS
// ==========================================
const USER_CREATION_PROMPTS = "i need you to pull up everything you can about my hyperspherical systems and project tesseract please you will have to check with gemini and github";

// ==========================================
// 2. 48-CHARACTER 3-TIER SCORING
// ==========================================
const TIER_LOWER = ['E','T','J','/','6','}','X','S','>','Q','8','0','Y','C','<','{'];
const TIER_MIDDLE = ['A','O','P','D','U','L','F','5','2','B','G','_','R','[','7','9'];
const TIER_UPPER = ['I','N',';',']','Z','=',')','H','4','K','V','(','M','1','W','3'];
const CHAR_SCORE_MAP = {};
TIER_LOWER.forEach((c,i)=>{CHAR_SCORE_MAP[c]=i+1;});
TIER_MIDDLE.forEach((c,i)=>{CHAR_SCORE_MAP[c]=i+17;});
TIER_UPPER.forEach((c,i)=>{CHAR_SCORE_MAP[c]=i+33;});
CHAR_SCORE_MAP[' ']=0; CHAR_SCORE_MAP['~']=0;

// ==========================================
// 3. 5+1 HOMOPHONIC SCRIPTS
// ==========================================
const SL = {
  latin:{A:'A',B:'B',C:'C',D:'D',E:'E',F:'F',G:'G',H:'H',I:'I',J:'J',K:'K',L:'L',M:'M',N:'N',O:'O',P:'P',Q:'Q',R:'R',S:'S',T:'T',U:'U',V:'V',W:'W',X:'X',Y:'Y',Z:'Z','0':'0','1':'1','2':'2','3':'3','4':'4','5':'5','6':'6','7':'7','8':'8','9':'9','{':'{','}':'}','[':'[',']':']','(':'(',')':')','\x3c':'\x3c','\x3e':'\x3e','=':'=',';':';','_':'_','/':'/','~':'~',' ':' '},
  greek:{A:'Α',B:'Β',C:'Γ',D:'Δ',E:'Ε',F:'Ζ',G:'Η',H:'Θ',I:'Ι',J:'Κ',K:'Λ',L:'Μ',M:'Ν',N:'Ξ',O:'Ο',P:'Π',Q:'Ρ',R:'Σ',S:'Υ',T:'Τ',U:'Φ',V:'Χ',W:'Ψ',X:'Ω',Y:'α',Z:'β','0':'γ','1':'δ','2':'ε','3':'ζ','4':'η','5':'θ','6':'ι','7':'κ','8':'λ','9':'μ','{':'⟨','}':'⟩','[':'⟦',']':'⟧','(':'⟮',')':'⟯','\x3c':'«','\x3e':'»','=':'≡',';':'·','_':'―','/':'⁄','~':'☉',' ':'·'},
  sanskrit:{A:'अ',B:'ब',C:'क',D:'द',E:'ए',F:'फ',G:'ग',H:'ह',I:'इ',J:'ज',K:'ख',L:'ल',M:'म',N:'न',O:'ओ',P:'प',Q:'घ',R:'र',S:'स',T:'त',U:'उ',V:'व',W:'श',X:'ष',Y:'य',Z:'ध','0':'०','1':'१','2':'२','3':'३','4':'४','5':'५','6':'६','7':'७','8':'८','9':'९','{':'ᳮ','}':'ᳯ','[':'ᳰ',']':'ᳱ','(':'ᳲ',')':'ᳳ','\x3c':'‹','\x3e':'›','=':'॥',';':'।','_':'्','/':'ॽ','~':'॰',' ':'⁞'},
  hieroglyph:{A:'𓂝',B:'𓃀',C:'𓎡',D:'𓂧',E:'𓇋',F:'𓆑',G:'𓎼',H:'𓉔',I:'𓇌',J:'𓆓',K:'𓐍',L:'𓃭',M:'𓅓',N:'𓈖',O:'𓍯',P:'𓊪',Q:'𓏘',R:'𓂋',S:'𓋴',T:'𓏏',U:'𓅱',V:'𓆗',W:'𓅷',X:'𓊃',Y:'𓇠',Z:'𓈎','0':'𓏺','1':'𓏻','2':'𓏼','3':'𓏽','4':'𓏾','5':'𓏿','6':'𓐀','7':'𓐁','8':'𓐂','9':'𓐃','{':'𓉐','}':'𓉑','[':'𓊖',']':'𓊗','(':'𓋹',')':'𓍑','\x3c':'𓂻','\x3e':'𓂼','=':'𓊢',';':'𓏶','_':'𓏲','/':'𓐎','~':'𓇩',' ':'𓎱'},
  cuneiform:{A:'𒀀',B:'𒁀',C:'𒅗',D:'𒁕',E:'𒂊',F:'𒉿',G:'𒂵',H:'𒄩',I:'𒄿',J:'𒅀',K:'𒆕',L:'𒆷',M:'𒈠',N:'𒈾',O:'𒌋',P:'𒉺',Q:'𒋡',R:'𒊏',S:'𒊓',T:'𒋫',U:'𒌑',V:'𒊑',W:'𒊒',X:'𒀝',Y:'𒅋',Z:'𒍝','0':'𒐀','1':'𒐕','2':'𒐖','3':'𒐗','4':'𒐘','5':'𒐙','6':'𒐚','7':'𒐛','8':'𒐜','9':'𒐝','{':'⦕','}':'⦖','[':'⸂',']':'⸃','(':'⸄',')':'⸅','\x3c':'◄','\x3e':'►','=':'𒀸',';':'𒑱','_':'ـ','/':'𒑰','~':'𒑲',' ':'𒑴'},
  nordic:{A:'ᚨ',B:'ᛒ',C:'ᚲ',D:'ᛞ',E:'ᛖ',F:'ᚠ',G:'ᚷ',H:'ᚺ',I:'ᛁ',J:'ᛃ',K:'ᚴ',L:'ᛚ',M:'ᛗ',N:'ᚾ',O:'ᛟ',P:'ᛈ',Q:'ᛜ',R:'ᚱ',S:'ᛋ',T:'ᛏ',U:'ᚢ',V:'ᚹ',W:'ᚦ',X:'ᛉ',Y:'ᛇ',Z:'ᛎ','0':'ᛦ','1':'ᛧ','2':'ᛨ','3':'ᛩ','4':'ᛪ','5':'᛫','6':'᛬','7':'᛭','8':'ᛮ','9':'ᛯ','{':'ᛐ','}':'ᛑ','[':'ᛒ',']':'ᛓ','(':'ᛔ',')':'ᛕ','\x3c':'ᛖ','\x3e':'ᛗ','=':'ᛘ',';':'ᛙ','_':'ᛚ','/':'ᛛ','~':'ᛝ',' ':'᛫'}
};
const SC = ['latin','greek','sanskrit','hieroglyph','cuneiform','nordic'];
const SR = {};
SC.forEach(s=>{SR[s]={};for(const[k,v] of Object.entries(SL[s])){SR[s][v]=k;}});

// ==========================================
// 4. LEXICAL PRUNER
// ==========================================
const PREPS = new Set(['about','above','across','after','against','along','among','around','at','before','behind','below','beneath','beside','between','beyond','by','down','during','except','for','from','in','inside','into','near','of','off','on','onto','out','outside','over','past','since','through','throughout','till','to','toward','towards','under','underneath','until','up','upon','with','within','without','the','a','an','and','is','are','it']);
function pruneText(t){
  if(!t)return{originalTokens:0,optimizedLength:0,strippedCount:0,optimizedText:''};
  const w=t.split(/\s+/);let sc=0;const o=[];
  for(const x of w){const c=x.toLowerCase().replace(/[^a-z0-9_{}\[\]()<>=;,\/]/g,'');if(PREPS.has(c)&&w.length>5)sc++;else if(c.length>0)o.push(c.toUpperCase());}
  const r=o.join('');return{originalTokens:w.length,optimizedLength:r.length,strippedCount:sc,optimizedText:r};
}

// ==========================================
// 5. CUBE SIZING
// ==========================================
function findDim(n){for(let d=5;d<=20;d++){if(d*d*d>=n)return d;}return 20;}

// ==========================================
// 6. 2D CENTER-OUT SQUARE SPIRAL
// Starts at dead center: (floor(size/2), floor(size/2))
// Grows outward: up 1, right 1, down 2, left 2, up 3, right 3, down 4, left 4...
// ==========================================
function centerOutSpiral2D(size, cw = true) {
  const coords = [];
  const cx = Math.floor(size / 2);
  const cy = Math.floor(size / 2);
  coords.push({ x: cx, y: cy }); // DEAD CENTER is position 0

  // CW: up, right, down, left
  // CCW: up, left, down, right
  const dirsCW  = [{ dx: 0, dy: -1 }, { dx: 1, dy: 0 }, { dx: 0, dy: 1 }, { dx: -1, dy: 0 }];
  const dirsCCW = [{ dx: 0, dy: -1 }, { dx: -1, dy: 0 }, { dx: 0, dy: 1 }, { dx: 1, dy: 0 }];
  const dirs = cw ? dirsCW : dirsCCW;

  let x = cx, y = cy;
  let dirIdx = 0;
  let stepLength = 1;
  let stepCount = 0;

  while (coords.length < size * size) {
    for (let s = 0; s < stepLength; s++) {
      x += dirs[dirIdx].dx;
      y += dirs[dirIdx].dy;
      if (x >= 0 && x < size && y >= 0 && y < size) {
        coords.push({ x, y });
        if (coords.length >= size * size) break;
      }
    }
    dirIdx = (dirIdx + 1) % 4;
    stepCount++;
    if (stepCount % 2 === 0) stepLength++;
  }

  return coords;
}

// ==========================================
// 7. 3D CENTER-OUT INGRESS PATH
// Cycles X -> Y -> Z -> X -> Y -> Z
// Each plane starts from the center layer and alternates out:
//   center, center+1, center-1, center+2, center-2, ...
// This means the 3D fill starts at the DEAD CENTER VOXEL of the cube
// and radiates outward in all 3 dimensions simultaneously.
// ==========================================
function centerOutIngressPath3D(dim, cw = true, planeSeq = ['X', 'Y', 'Z']) {
  const total = dim * dim * dim;
  const spiral2D = centerOutSpiral2D(dim, cw);
  const path = [];
  const visited = new Set();

  // Generate center-out layer order: center, center+1, center-1, center+2, ...
  const centerLayer = Math.floor(dim / 2);
  const layerOrder = [centerLayer];
  for (let offset = 1; offset < dim; offset++) {
    if (centerLayer + offset < dim) layerOrder.push(centerLayer + offset);
    if (centerLayer - offset >= 0) layerOrder.push(centerLayer - offset);
  }

  let planeIdx = 0;
  let layerIdx = 0;

  while (path.length < total && layerIdx < layerOrder.length) {
    const layer = layerOrder[layerIdx];
    const plane = planeSeq[planeIdx % planeSeq.length];

    for (const pt of spiral2D) {
      let vx, vy, vz;
      if (plane === 'X') { vx = layer; vy = pt.x; vz = pt.y; }
      else if (plane === 'Y') { vx = pt.x; vy = layer; vz = pt.y; }
      else { vx = pt.x; vy = pt.y; vz = layer; }

      const key = `${vx},${vy},${vz}`;
      if (!visited.has(key)) {
        visited.add(key);
        path.push({ x: vx, y: vy, z: vz, plane });
      }
    }

    planeIdx++;
    if (planeIdx % planeSeq.length === 0) layerIdx++;
  }

  return path;
}

// ==========================================
// 8. 4-CORNER TOP-DOWN UNWRAP
// ==========================================
function unwrapPath4Corner(dim) {
  const p = [];
  for (let z = dim - 1; z >= 0; z--) {
    const pi = (dim - 1) - z, cm = pi % 4;
    if (cm === 0) { for (let y = 0; y < dim; y++) for (let x = 0; x < dim; x++) p.push({ x, y, z }); }
    else if (cm === 1) { for (let y = 0; y < dim; y++) for (let x = dim - 1; x >= 0; x--) p.push({ x, y, z }); }
    else if (cm === 2) { for (let x = dim - 1; x >= 0; x--) for (let y = dim - 1; y >= 0; y--) p.push({ x, y, z }); }
    else { for (let x = 0; x < dim; x++) for (let y = 0; y < dim; y++) p.push({ x, y, z }); }
  }
  return p;
}

// ==========================================
// 9. ENGINE CLASS
// ==========================================
class TesseractEngine {
  constructor() {
    this.dim = 5; this.totalVoxels = 125; this.cube = []; this.ingressPath = []; this.unwrapPath = [];
    this.avgScore = 0; this.routingMode = ''; this.payloadLength = 0;
    this.lastRuneArray = []; this.lastOptText = ''; this.isClockwise = true; this.planeSeq = ['X', 'Y', 'Z'];
  }
  initCube(dim) {
    this.dim = dim; this.totalVoxels = dim * dim * dim;
    this.cube = Array.from({ length: dim }, () => Array.from({ length: dim }, () => Array(dim).fill(' ')));
    this.unwrapPath = unwrapPath4Corner(dim);
  }
  computeRouting(text) {
    let ts = 0, sc = 0;
    for (const c of text) { if (CHAR_SCORE_MAP[c] !== undefined && c !== ' ' && c !== '~') { ts += CHAR_SCORE_MAP[c]; sc++; } }
    this.avgScore = sc > 0 ? (ts / sc) : 24;
    if (this.avgScore <= 16) { this.isClockwise = false; this.planeSeq = ['X', 'Y', 'Z']; this.routingMode = 'LOWER 1/3: CCW Spiral (X➔Y➔Z)'; }
    else if (this.avgScore <= 32) { this.isClockwise = false; this.planeSeq = ['Z', 'Y', 'X']; this.routingMode = 'MIDDLE 1/3: PING-PONG FLIP (Z➔Y➔X)'; }
    else { this.isClockwise = true; this.planeSeq = ['X', 'Y', 'Z']; this.routingMode = 'UPPER 1/3: CW Spiral (X➔Y➔Z)'; }
  }
  encode(optText) {
    this.lastOptText = optText;
    const stream = optText + '~';
    this.payloadLength = stream.length;
    const dim = findDim(this.payloadLength);
    this.initCube(dim);
    this.computeRouting(optText);
    this.ingressPath = centerOutIngressPath3D(dim, this.isClockwise, this.planeSeq);
    for (let i = 0; i < this.totalVoxels; i++) { const n = this.ingressPath[i]; this.cube[n.z][n.y][n.x] = i < stream.length ? stream[i] : ' '; }
    const uw = []; for (const n of this.unwrapPath) uw.push(this.cube[n.z][n.y][n.x] || ' ');
    const uw1D = uw.join('');
    const ra = []; for (let i = 0; i < uw1D.length; i++) { ra.push(SL[SC[i % SC.length]][uw1D[i]] || uw1D[i]); }
    this.lastRuneArray = ra;
    return { dim, unwrappedStream: uw1D, runesString: ra.join(''), runeArray: ra, avgScore: this.avgScore, routingMode: this.routingMode };
  }
  decode(runeArr) {
    if (!runeArr || runeArr.length === 0) return '';
    const raw = [];
    for (let i = 0; i < runeArr.length; i++) { raw.push(SR[SC[i % SC.length]][runeArr[i]] || runeArr[i]); }
    const tl = raw.length; const dd = Math.round(Math.cbrt(tl)) || findDim(tl);
    const dt = dd * dd * dd; const uo = unwrapPath4Corner(dd);
    const rc = Array.from({ length: dd }, () => Array.from({ length: dd }, () => Array(dd).fill(' ')));
    for (let i = 0; i < uo.length && i < raw.length; i++) { const n = uo[i]; rc[n.z][n.y][n.x] = raw[i]; }
    let ds = 0, dc = 0;
    for (const c of raw) { if (c !== ' ' && c !== '~' && CHAR_SCORE_MAP[c] !== undefined) { ds += CHAR_SCORE_MAP[c]; dc++; } }
    const da = dc > 0 ? (ds / dc) : 24;
    let cw = true, ps = ['X', 'Y', 'Z'];
    if (da <= 16) { cw = false; ps = ['X', 'Y', 'Z']; } else if (da <= 32) { cw = false; ps = ['Z', 'Y', 'X']; } else { cw = true; ps = ['X', 'Y', 'Z']; }
    const ip = centerOutIngressPath3D(dd, cw, ps);
    const rec = [];
    for (let i = 0; i < dt; i++) { const n = ip[i]; const c = rc[n.z][n.y][n.x]; if (c === '~') break; if (c && c !== ' ') rec.push(c); }
    return rec.join('');
  }
}

// ==========================================
// 10. THREE.JS 3D VIEWPORT
// ==========================================
let scene, camera, renderer, controls;
let voxelMeshes = {};
let pathLine, trailLines = [], activeEngine = new TesseractEngine(), autoRotate = true;
let centerMarker = null;

function init3DViewport() {
  const container = document.getElementById('canvas3DContainer');
  if (!container) return;
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x07090e);
  camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
  camera.position.set(32, 26, 40);
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);
  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.05;
  controls.autoRotate = autoRotate; controls.autoRotateSpeed = 0.8;
  scene.add(new THREE.AmbientLight(0xffffff, 0.85));
  const d1 = new THREE.DirectionalLight(0x38bdf8, 0.9); d1.position.set(30, 50, 30); scene.add(d1);
  const d2 = new THREE.DirectionalLight(0xf59e0b, 0.6); d2.position.set(-30, -30, -30); scene.add(d2);
  window.addEventListener('resize', () => { camera.aspect = container.clientWidth / container.clientHeight; camera.updateProjectionMatrix(); renderer.setSize(container.clientWidth, container.clientHeight); });
  (function animate() { requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); })();
  const ol = document.getElementById('loadingOverlay'); if (ol) ol.style.display = 'none';
}

function clearScene() {
  Object.values(voxelMeshes).forEach(m => scene.remove(m)); voxelMeshes = {};
  if (pathLine) { scene.remove(pathLine); pathLine = null; }
  trailLines.forEach(l => scene.remove(l)); trailLines = [];
  if (centerMarker) { scene.remove(centerMarker); centerMarker = null; }
  const f = scene.getObjectByName('cubeFrame'); if (f) scene.remove(f);
}

function drawCubeFrame(dim) {
  const g = new THREE.BoxGeometry(dim, dim, dim);
  const e = new THREE.EdgesGeometry(g);
  const l = new THREE.LineSegments(e, new THREE.LineBasicMaterial({ color: 0x243049, transparent: true, opacity: 0.6 }));
  l.name = 'cubeFrame'; scene.add(l);
}

function addCenterMarker(dim) {
  const half = (dim - 1) / 2;
  const geo = new THREE.SphereGeometry(0.7, 16, 16);
  const mat = new THREE.MeshBasicMaterial({ color: 0xf59e0b, transparent: true, opacity: 0.9 });
  centerMarker = new THREE.Mesh(geo, mat);
  centerMarker.position.set(0, 0, 0); // Dead center of the cube
  scene.add(centerMarker);

  // Add glow ring
  const ringGeo = new THREE.RingGeometry(0.8, 1.2, 32);
  const ringMat = new THREE.MeshBasicMaterial({ color: 0xf59e0b, transparent: true, opacity: 0.4, side: THREE.DoubleSide });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.position.copy(centerMarker.position);
  scene.add(ring);
  trailLines.push(ring);
}

function addVoxel(x, y, z, dim, color, opacity) {
  const half = (dim - 1) / 2;
  const geo = new THREE.BoxGeometry(0.78, 0.78, 0.78);
  const mat = new THREE.MeshLambertMaterial({ color, transparent: true, opacity });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.set(x - half, y - half, z - half);
  scene.add(mesh);
  voxelMeshes[`${x},${y},${z}`] = mesh;
  return mesh;
}

function setVoxelColor(x, y, z, color, opacity) {
  const m = voxelMeshes[`${x},${y},${z}`];
  if (m) { m.material.color.set(color); m.material.opacity = opacity; }
}

function addTrailSegment(x1, y1, z1, x2, y2, z2, dim, color) {
  const half = (dim - 1) / 2;
  const pts = [
    new THREE.Vector3(x1 - half, y1 - half, z1 - half),
    new THREE.Vector3(x2 - half, y2 - half, z2 - half)
  ];
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.6 });
  const line = new THREE.Line(geo, mat);
  scene.add(line);
  trailLines.push(line);
}

// ==========================================
// 11. SPEED CONTROL
// ==========================================
const SPEED_TABLE = [1, 2, 5, 10, 25, 50, 100, 250, 500];
function getDelay() { return SPEED_TABLE[parseInt(document.getElementById('sliderSpeed').value)] || 10; }
function updateSpeedLabel() {
  const v = parseInt(document.getElementById('sliderSpeed').value);
  const labels = ['1ms Lightning', '2ms Blitz', '5ms Fast', '10ms Normal', '25ms Detailed', '50ms Slow', '100ms Cinematic', '250ms Frame-by-Frame', '500ms Ultra-Slow'];
  document.getElementById('speedLabel').innerText = labels[v] || '';
}
function setProgress(pct) { document.getElementById('progressBar').style.width = `${pct}%`; }
function setPhase(t) { document.getElementById('phaseLabel').innerText = t; document.getElementById('badgePhase').innerText = `PHASE: ${t}`; }
function setCharLabel(t) { const el = document.getElementById('flyingCharLabel'); el.innerText = t; el.classList.toggle('visible', !!t); }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ==========================================
// 12. ANIMATED FULL PIPELINE
// ==========================================
let animating = false;

async function runAnimatedPipeline(inputText) {
  if (animating) return;
  animating = true;
  document.getElementById('btnAnimate').disabled = true;
  document.getElementById('btnInstant').disabled = true;

  // Phase 1: Lexical Pruning
  setPhase('LEXICAL PRUNING'); setProgress(2);
  const opt = pruneText(inputText);
  document.getElementById('cntOriginal').innerText = opt.originalTokens;
  document.getElementById('cntOptimized').innerText = opt.optimizedLength;
  document.getElementById('cntStripped').innerText = opt.strippedCount;
  document.getElementById('outOptimized').innerText = opt.optimizedText;
  await sleep(300);

  // Phase 2: Compute
  setPhase('COMPUTING 3-TIER SCORE'); setProgress(5);
  activeEngine = new TesseractEngine();
  const stream = opt.optimizedText + '~';
  const dim = findDim(stream.length);
  activeEngine.lastOptText = opt.optimizedText;
  activeEngine.payloadLength = stream.length;
  activeEngine.initCube(dim);
  activeEngine.computeRouting(opt.optimizedText);
  activeEngine.ingressPath = centerOutIngressPath3D(dim, activeEngine.isClockwise, activeEngine.planeSeq);

  document.getElementById('badgeDim').innerText = `ADAPTIVE DIM: ${dim}×${dim}×${dim} (${dim ** 3} VOXELS)`;
  document.getElementById('avgScoreDisplay').innerText = `AVG SCORE: ${activeEngine.avgScore.toFixed(2)} / 48`;
  document.getElementById('tierIndicator').style.left = `${Math.min(100, (activeEngine.avgScore / 48) * 100)}%`;
  document.getElementById('tierVerdict').innerText = activeEngine.routingMode;
  await sleep(400);

  // Phase 3: BUILD CUBE FROM CENTER OUT
  setPhase('BUILDING FROM CENTER OUT'); setProgress(8);
  clearScene();
  drawCubeFrame(dim);
  addCenterMarker(dim);

  // Add transparent void voxels
  for (let z = 0; z < dim; z++) for (let y = 0; y < dim; y++) for (let x = 0; x < dim; x++) {
    addVoxel(x, y, z, dim, 0x1e293b, 0.03);
  }

  const delay = getDelay();
  const batch = Math.max(1, Math.floor(40 / Math.max(1, delay / 5)));
  let prevNode = null;

  for (let i = 0; i < activeEngine.ingressPath.length; i++) {
    const node = activeEngine.ingressPath[i];
    const char = i < stream.length ? stream[i] : ' ';
    activeEngine.cube[node.z][node.y][node.x] = char;

    if (char !== ' ') {
      const score = CHAR_SCORE_MAP[char] || 0;
      let finalColor = 0x1e293b;
      if (score <= 16) finalColor = 0x10b981;
      else if (score <= 32) finalColor = 0xf59e0b;
      else finalColor = 0x3b82f6;

      // Flash white on arrival
      setVoxelColor(node.x, node.y, node.z, 0xffffff, 1.0);
      setCharLabel(`${char} → [${node.x},${node.y},${node.z}]`);

      // Draw trail from previous position
      if (prevNode) {
        addTrailSegment(prevNode.x, prevNode.y, prevNode.z, node.x, node.y, node.z, dim, 0xec4899);
      }
      prevNode = node;

      // Fade to tier color after brief flash
      const fc = finalColor;
      setTimeout(() => setVoxelColor(node.x, node.y, node.z, fc, 0.9), Math.min(delay * 2, 200));
    }

    if (i % batch === 0) {
      setProgress(8 + (i / activeEngine.ingressPath.length) * 32);
      await sleep(delay);
    }
  }

  setCharLabel('');
  setProgress(40);
  await sleep(200);

  // Phase 4: STRIP CUBE (4-Corner Unwrap)
  setPhase('4-CORNER UNWRAP STRIPPING');
  const unwrappedChars = [];
  const stripDisplay = document.getElementById('outUnwrap');
  stripDisplay.innerText = '';

  for (let i = 0; i < activeEngine.unwrapPath.length; i++) {
    const node = activeEngine.unwrapPath[i];
    const char = activeEngine.cube[node.z][node.y][node.x] || ' ';
    unwrappedChars.push(char);

    if (char !== ' ') {
      setVoxelColor(node.x, node.y, node.z, 0xec4899, 1.0);
      setCharLabel(char);
      const nx = node.x, ny = node.y, nz = node.z;
      setTimeout(() => setVoxelColor(nx, ny, nz, 0x1e293b, 0.05), Math.min(delay * 3, 300));
    }

    if (i % batch === 0) {
      stripDisplay.innerText = unwrappedChars.join('').slice(-200);
      setProgress(40 + (i / activeEngine.unwrapPath.length) * 25);
      await sleep(delay);
    }
  }

  stripDisplay.innerText = unwrappedChars.join('');
  setCharLabel(''); setProgress(65);
  await sleep(200);

  // Phase 5: 5+1 HOMOPHONIC ENCODING
  setPhase('5+1 HOMOPHONIC ENCODING');
  const uw1D = unwrappedChars.join('');
  const runeArray = [];
  const runeDisplay = document.getElementById('outRunes');
  runeDisplay.innerText = '';

  for (let i = 0; i < uw1D.length; i++) {
    const char = uw1D[i];
    const sn = SC[i % SC.length];
    const glyph = SL[sn][char] || char;
    runeArray.push(glyph);

    if (char !== ' ') setCharLabel(`${char} → ${glyph} [${sn.toUpperCase()}]`);

    if (i % (batch * 3) === 0) {
      runeDisplay.innerText = runeArray.join('').slice(-300);
      setProgress(65 + (i / uw1D.length) * 15);
      await sleep(delay);
    }
  }

  runeDisplay.innerText = runeArray.join('');
  activeEngine.lastRuneArray = runeArray;
  setCharLabel(''); setProgress(80);
  await sleep(300);

  // Phase 6: DECODE (Reverse)
  setPhase('DECODING: DE-CIPHER RUNES');

  const rawChars = [];
  for (let i = 0; i < runeArray.length; i++) { rawChars.push(SR[SC[i % SC.length]][runeArray[i]] || runeArray[i]); }
  setProgress(83);
  await sleep(200);

  // Rebuild cube
  setPhase('REBUILDING CUBE FROM STREAM');
  clearScene(); drawCubeFrame(dim); addCenterMarker(dim);
  for (let z = 0; z < dim; z++) for (let y = 0; y < dim; y++) for (let x = 0; x < dim; x++) {
    addVoxel(x, y, z, dim, 0x1e293b, 0.03);
  }

  const decUO = unwrapPath4Corner(dim);
  const decCube = Array.from({ length: dim }, () => Array.from({ length: dim }, () => Array(dim).fill(' ')));

  for (let i = 0; i < decUO.length && i < rawChars.length; i++) {
    const node = decUO[i];
    decCube[node.z][node.y][node.x] = rawChars[i];
    if (rawChars[i] !== ' ') {
      setVoxelColor(node.x, node.y, node.z, 0x34d399, 0.9);
      setCharLabel(rawChars[i]);
    }
    if (i % batch === 0) { setProgress(83 + (i / decUO.length) * 8); await sleep(delay); }
  }

  setCharLabel(''); setProgress(91);
  await sleep(200);

  // Read spiral path
  setPhase('READING CENTER-OUT SPIRAL');
  let ds = 0, dc = 0;
  for (const c of rawChars) { if (c !== ' ' && c !== '~' && CHAR_SCORE_MAP[c] !== undefined) { ds += CHAR_SCORE_MAP[c]; dc++; } }
  const da = dc > 0 ? (ds / dc) : 24;
  let cw = true, ps = ['X', 'Y', 'Z'];
  if (da <= 16) { cw = false; } else if (da <= 32) { cw = false; ps = ['Z', 'Y', 'X']; }
  const decIP = centerOutIngressPath3D(dim, cw, ps);

  const recovered = [];
  for (let i = 0; i < dim * dim * dim; i++) {
    const node = decIP[i];
    const c = decCube[node.z][node.y][node.x];
    if (c === '~') break;
    if (c && c !== ' ') {
      recovered.push(c);
      setVoxelColor(node.x, node.y, node.z, 0xffffff, 1.0);
      const nx = node.x, ny = node.y, nz = node.z;
      setTimeout(() => setVoxelColor(nx, ny, nz, 0x3b82f6, 0.9), Math.min(delay * 2, 200));
    }
    if (i % batch === 0) { setProgress(91 + (i / (dim * dim * dim)) * 8); await sleep(delay); }
  }

  const recoveredStr = recovered.join('');
  document.getElementById('outDecoded').innerText = recoveredStr;
  const isExact = (recoveredStr === opt.optimizedText);
  const ve = document.getElementById('verifyStatus');
  ve.innerText = isExact ? '100% LOSSLESS ROUNDTRIP VERIFIED (PERFECT MATCH)' : 'MISMATCH';
  ve.className = isExact ? 'text-success' : 'text-danger';

  setPhase(isExact ? 'COMPLETE ✓ PERFECT MATCH' : 'COMPLETE ✗ MISMATCH');
  setProgress(100); setCharLabel('');

  document.getElementById('cntPayload').innerText = activeEngine.payloadLength;
  document.getElementById('cntFillers').innerText = activeEngine.totalVoxels - activeEngine.payloadLength;
  document.getElementById('cubeInterleaveStats').innerHTML = `
    <strong>Cube:</strong> ${dim}×${dim}×${dim} (${dim ** 3} Voxels)<br>
    <strong>Fill:</strong> ${((activeEngine.payloadLength / activeEngine.totalVoxels) * 100).toFixed(1)}%<br>
    <strong>Spiral Origin:</strong> Dead Center [${Math.floor(dim / 2)},${Math.floor(dim / 2)},${Math.floor(dim / 2)}]<br>
    <strong>Routing:</strong> ${activeEngine.routingMode}<br>
    <strong>Unwrap:</strong> 4-Corner Top-Down (z=${dim - 1}→z=0)`;

  animating = false;
  document.getElementById('btnAnimate').disabled = false;
  document.getElementById('btnInstant').disabled = false;
}

// ==========================================
// 13. INSTANT PIPELINE
// ==========================================
function runInstantPipeline(inputText) {
  if (!inputText || !inputText.trim()) return;
  const opt = pruneText(inputText);
  document.getElementById('cntOriginal').innerText = opt.originalTokens;
  document.getElementById('cntOptimized').innerText = opt.optimizedLength;
  document.getElementById('cntStripped').innerText = opt.strippedCount;
  document.getElementById('outOptimized').innerText = opt.optimizedText;

  activeEngine = new TesseractEngine();
  const res = activeEngine.encode(opt.optimizedText);

  document.getElementById('badgeDim').innerText = `ADAPTIVE DIM: ${res.dim}×${res.dim}×${res.dim} (${res.dim ** 3} VOXELS)`;
  document.getElementById('avgScoreDisplay').innerText = `AVG SCORE: ${res.avgScore.toFixed(2)} / 48`;
  document.getElementById('tierIndicator').style.left = `${Math.min(100, (res.avgScore / 48) * 100)}%`;
  document.getElementById('tierVerdict').innerText = res.routingMode;
  document.getElementById('outUnwrap').innerText = res.unwrappedStream;
  document.getElementById('outRunes').innerText = res.runesString;
  document.getElementById('cntPayload').innerText = activeEngine.payloadLength;
  document.getElementById('cntFillers').innerText = activeEngine.totalVoxels - activeEngine.payloadLength;

  clearScene(); drawCubeFrame(activeEngine.dim); addCenterMarker(activeEngine.dim);
  const dim = activeEngine.dim;
  for (let z = 0; z < dim; z++) for (let y = 0; y < dim; y++) for (let x = 0; x < dim; x++) {
    const ch = activeEngine.cube[z][y][x]; const isP = ch && ch !== ' ';
    const sc = CHAR_SCORE_MAP[ch] || 0;
    let col = 0x1e293b;
    if (isP) { if (sc <= 16) col = 0x10b981; else if (sc <= 32) col = 0xf59e0b; else col = 0x3b82f6; }
    addVoxel(x, y, z, dim, col, isP ? 0.9 : 0.05);
  }

  // Draw full spiral trail
  const half = (dim - 1) / 2;
  const trailPts = [];
  for (let i = 0; i < Math.min(activeEngine.payloadLength, activeEngine.ingressPath.length); i++) {
    const n = activeEngine.ingressPath[i];
    trailPts.push(new THREE.Vector3(n.x - half, n.y - half, n.z - half));
  }
  if (trailPts.length > 1) {
    const geo = new THREE.BufferGeometry().setFromPoints(trailPts);
    const mat = new THREE.LineBasicMaterial({ color: 0xec4899, transparent: true, opacity: 0.5 });
    pathLine = new THREE.Line(geo, mat);
    scene.add(pathLine);
  }

  const recovered = activeEngine.decode(res.runeArray);
  document.getElementById('outDecoded').innerText = recovered;
  const isExact = (recovered === opt.optimizedText);
  const ve = document.getElementById('verifyStatus');
  ve.innerText = isExact ? '100% LOSSLESS ROUNDTRIP VERIFIED (PERFECT MATCH)' : 'MISMATCH';
  ve.className = isExact ? 'text-success' : 'text-danger';
  setPhase(isExact ? 'INSTANT ✓ PERFECT MATCH' : 'INSTANT ✗ MISMATCH');
  setProgress(100);

  document.getElementById('cubeInterleaveStats').innerHTML = `
    <strong>Cube:</strong> ${dim}×${dim}×${dim} (${dim ** 3} Voxels)<br>
    <strong>Fill:</strong> ${((activeEngine.payloadLength / activeEngine.totalVoxels) * 100).toFixed(1)}%<br>
    <strong>Spiral Origin:</strong> Dead Center [${Math.floor(dim / 2)},${Math.floor(dim / 2)},${Math.floor(dim / 2)}]<br>
    <strong>Routing:</strong> ${activeEngine.routingMode}<br>
    <strong>Unwrap:</strong> 4-Corner Top-Down (z=${dim - 1}→z=0)`;
}

// ==========================================
// 14. DOM INIT
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
  init3DViewport();
  updateSpeedLabel();

  const promptInput = document.getElementById('promptInput');

  document.getElementById('btnLoadUserPrompts').addEventListener('click', () => {
    promptInput.value = USER_CREATION_PROMPTS;
    runInstantPipeline(promptInput.value);
  });

  document.getElementById('btnAnimate').addEventListener('click', () => {
    runAnimatedPipeline(promptInput.value.trim() || USER_CREATION_PROMPTS);
  });

  document.getElementById('btnInstant').addEventListener('click', () => {
    runInstantPipeline(promptInput.value.trim() || USER_CREATION_PROMPTS);
  });

  document.getElementById('btnReset').addEventListener('click', () => {
    promptInput.value = '';
    ['outOptimized', 'outUnwrap', 'outRunes', 'outDecoded'].forEach(id => document.getElementById(id).innerText = '');
    document.getElementById('verifyStatus').innerText = 'AWAITING INPUT';
    setPhase('Ready'); setProgress(0); setCharLabel('');
  });

  document.getElementById('btnAutoRotate').addEventListener('click', () => {
    autoRotate = !autoRotate; controls.autoRotate = autoRotate;
    document.getElementById('btnAutoRotate').innerText = `Auto-Rotate: ${autoRotate ? 'ON' : 'OFF'}`;
  });

  document.getElementById('btnResetCamera').addEventListener('click', () => {
    camera.position.set(32, 26, 40); controls.target.set(0, 0, 0);
  });

  document.getElementById('sliderSpeed').addEventListener('input', updateSpeedLabel);

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const target = document.getElementById(btn.dataset.tab);
      if (target) target.classList.add('active');
    });
  });

  ['sliderSliceX', 'sliderSliceY', 'sliderSliceZ'].forEach(id => {
    const slider = document.getElementById(id);
    const label = document.getElementById(id.replace('slider', 'val'));
    slider.addEventListener('input', () => { label.innerText = slider.value === '-1' ? 'ALL' : slider.value; });
  });

  promptInput.value = USER_CREATION_PROMPTS;
  runInstantPipeline(promptInput.value);
});
