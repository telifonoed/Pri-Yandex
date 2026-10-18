
(function(){
  try {
  // ---- per-document random seed: values stable within page, unique per visit ----
  var seed = 0;
  try {
    var buf = new Uint32Array(1);
    (window.crypto||window.msCrypto).getRandomValues(buf);
    seed = buf[0] || 12345;
  } catch(e){ seed = Math.floor(Math.random()*4294967295); }
  function rnd(){
    seed ^= seed << 13; seed >>>= 0;
    seed ^= seed >> 17;
    seed ^= seed << 5;  seed >>>= 0;
    return seed / 4294967296;
  }
  function pick(a){ return a[Math.floor(rnd()*a.length)]; }
  function jit(base, amp){ return base + (rnd()-0.5)*amp; }

  // ---- automation / locale ----
  try { Object.defineProperty(navigator, 'webdriver', {get: function(){return undefined;}, configurable:true}); } catch(e){}
  try { Object.defineProperty(navigator, 'languages', {get: function(){return ['en-US','en'];}, configurable:true}); } catch(e){}
  try { Object.defineProperty(navigator, 'plugins', {get: function(){return [];}, configurable:true}); } catch(e){}
  try { Object.defineProperty(navigator, 'mimeTypes', {get: function(){return [];}, configurable:true}); } catch(e){}
  try { Object.defineProperty(navigator, 'platform', {get: function(){return 'Win32';}, configurable:true}); } catch(e){}
  try { Object.defineProperty(navigator, 'maxTouchPoints', {get: function(){return 0;}, configurable:true}); } catch(e){}

  // ---- hardware profile: randomize so it is not a stable ID ----
  try { var cores = pick([2,4,8,12,16]);
        Object.defineProperty(navigator, 'hardwareConcurrency', {get: function(){return cores;}, configurable:true}); } catch(e){}
  try { var mem = pick([2,4,8,16]);
        Object.defineProperty(navigator, 'deviceMemory', {get: function(){return mem;}, configurable:true}); } catch(e){}

  // ---- WebGL: generic pool + randomized numeric params ----
  // vendor + renderer must stay a consistent pair (real GPUs are never mixed)
  var GPUS = [
    ['Google Inc. (Intel)',  'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0)'],
    ['Google Inc. (Intel)',  'ANGLE (Intel, Intel(R) HD Graphics 630 Direct3D11 vs_5_0 ps_5_0)'],
    ['Google Inc. (Intel)',  'ANGLE (Intel, Intel(R) Iris(TM) Plus Graphics 655 Direct3D11 vs_5_0 ps_5_0)'],
    ['Google Inc. (NVIDIA)', 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0)'],
    ['Google Inc. (NVIDIA)', 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)'],
    ['Google Inc. (AMD)',    'ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0)'],
    ['Google Inc. (AMD)',    'ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0)'],
    ['Google Inc.',          'ANGLE (Qualcomm, Adreno (TM) 640, OpenGL ES 3.2 V@0530.0)']
  ];
  var g = pick(GPUS);
  var gVendor = g[0];
  var gRenderer = g[1];
  var maxTex = pick([2048,4096,8192,16384]);
  var maxVert = pick([16,32,64]);
  function patchGL(proto){
    if(!proto) return;
    var gp = proto.getParameter, ge = proto.getExtension;
    proto.getParameter = function(p){
      if (p === 37445) return gVendor;
      if (p === 37446) return gRenderer;
      if (p === 3379)  return maxTex;
      if (p === 35660) return maxTex;
      if (p === 35661) return maxVert;
      // NOTE: 0x1F00 (7936) = VENDOR, 0x1F01 (7937) = RENDERER,
      //       0x1F02 (7938) = VERSION, 0x8B8C (35724) = SHADING_LANGUAGE_VERSION
      if (p === 7936)  return gVendor;
      if (p === 7937)  return gRenderer;
      if (p === 7938)  return 'WebGL 1.0 (OpenGL ES 2.0 Chromium)';
      if (p === 35724) return 'WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)';
      if (p === 33902 || p === 33901) return 64.0;
      return gp.apply(this, arguments);
    };
    // Hide debug renderer info so raw strings cannot be read.
    proto.getExtension = function(name){
      if (String(name) === 'WEBGL_debug_renderer_info') return null;
      return ge.apply(this, arguments);
    };
    try {
      var gpd = proto.getProgramParameter;
      proto.getProgramParameter = function(p, pn){ return gpd.apply(this, arguments); };
    } catch(e){}
  }
  try { patchGL(window.WebGLRenderingContext && WebGLRenderingContext.prototype); } catch(e){}
  try { patchGL(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype); } catch(e){}

  // ---- Audio fingerprint ----
  try {
    var AN = window.AnalyserNode;
    if (AN && AN.prototype) {
      var gff = AN.prototype.getFloatFrequencyData;
      AN.prototype.getFloatFrequencyData = function(arr){
        gff.apply(this, arguments);
        for (var i=0;i<arr.length;i++){ if (isFinite(arr[i])) arr[i] = arr[i] + (rnd()-0.5)*1e-4; }
        return arr;
      };
      var gbf = AN.prototype.getByteFrequencyData;
      AN.prototype.getByteFrequencyData = function(arr){
        gbf.apply(this, arguments);
        for (var i=0;i<arr.length;i++){ if (rnd() > 0.995) arr[i] = Math.floor(rnd()*255); }
        return arr;
      };
      var gtd = AN.prototype.getFloatTimeDomainData;
      AN.prototype.getFloatTimeDomainData = function(arr){
        gtd.apply(this, arguments);
        for (var i=0;i<arr.length;i++){ if (isFinite(arr[i])) arr[i] = arr[i] + (rnd()-0.5)*1e-4; }
        return arr;
      };
    }
    var AB = window.AudioBuffer;
    if (AB && AB.prototype) {
      var gcd = AB.prototype.getChannelData;
      AB.prototype.getChannelData = function(){
        var d = gcd.apply(this, arguments);
        if (!this.__priNoised) {
          this.__priNoised = true;
          var n = Math.min(d.length, 2048);
          for (var i=0;i<n;i++){ if (isFinite(d[i])) d[i] = d[i] + (rnd()-0.5)*1e-6; }
        }
        return d;
      };
      var gcf = AB.prototype.copyFromChannel;
      AB.prototype.copyFromChannel = function(dest, ch, start){
        var r = gcf.apply(this, arguments);
        for (var i=0;i<dest.length;i++){ if (isFinite(dest[i])) dest[i] = dest[i] + (rnd()-0.5)*1e-6; }
        return r;
      };
    }
  } catch(e){}

  // ---- Font enumeration: only report a small generic set ----
  try {
    if (document.fonts) {
      var ALLOWED = /Arial|Times\s*New\s*Roman|Courier\s*New|Georgia|Verdana|Tahoma|sans-serif|serif|monospace|system-ui|-apple-system|Segoe\s*UI|ui-sans-serif|ui-serif|ui-monospace/i;
      document.fonts.check = function(font, text){
        var f = String(font || '');
        return ALLOWED.test(f);
      };
      document.fonts.load = function(){ return Promise.resolve([]); };
    }
  } catch(e){}

  // ---- Canvas + text measurement noise ----
  try {
    var origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(){
      try {
        var ctx = this.getContext('2d');
        if (ctx && this.width > 1 && this.height > 1) {
          var img = ctx.getImageData(0,0,this.width,this.height);
          for (var i=0;i<img.data.length;i+=4){ img.data[i] ^= (Math.random()*2)|0; }
          ctx.putImageData(img,0,0);
        }
      } catch(e){}
      return origToDataURL.apply(this, arguments);
    };
  } catch(e){}

  // ---- Battery / Connection ----
  try { if (navigator.getBattery) {
    navigator.getBattery = function(){ return Promise.resolve({charging:true, chargingTime:0, dischargingTime:Infinity, level:1}); };
  } } catch(e){}
  try { if (navigator.connection) {
    Object.defineProperty(navigator.connection, 'effectiveType', {get: function(){return '4g';}});
    Object.defineProperty(navigator.connection, 'downlink', {get: function(){return jit(10,2);}});
    Object.defineProperty(navigator.connection, 'rtt', {get: function(){return Math.round(jit(50,20));}});
  } } catch(e){}
  } catch(e){}
})();
