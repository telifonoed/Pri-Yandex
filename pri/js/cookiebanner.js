
(function(){
  const selectors = [
    '#cookie-banner','.cookie-banner','#cookie-notice','.cookie-notice',
    '#cookie-consent','.cookie-consent','#gdpr-banner','.gdpr-banner',
    '#onetrust-banner-sdk','#onetrust-consent-sdk','#CybotCookiebotDialog',
    '.cc-banner','.cc-window','#cookie-law-info-bar',
    '[id*="cookie-banner"]','[id*="cookie-consent"]','[id*="cookie-notice"]',
    '[class*="cookie-banner"]','[class*="cookie-consent"]','[class*="cookie-notice"]',
    '[id*="gdpr"]','[class*="gdpr"]','[aria-label*="cookie" i]',
    '#usercentrics-root','.uc-banner','[data-testid*="cookie"]',
    '.fc-consent-root','.fc-dialog','.qc-cmp2-container'
  ];
  function hide(){
    selectors.forEach(function(s){
      try { document.querySelectorAll(s).forEach(function(e){ e.remove(); }); } catch(e){}
    });
    // shadow DOM
    document.querySelectorAll('*').forEach(function(el){
      if (el.shadowRoot) {
        selectors.forEach(function(s){
          try { el.shadowRoot.querySelectorAll(s).forEach(function(e){ e.remove(); }); } catch(e){}
        });
      }
    });
    // click reject/decline
    document.querySelectorAll('button,a,[role="button"]').forEach(function(b){
      var t = (b.textContent||'').toLowerCase();
      if (t.indexOf('reject')>=0 || t.indexOf('decline')>=0 || t.indexOf('отклон')>=0 ||
          t.indexOf('отказ')>=0 || t.indexOf('только необходим')>=0 ||
          t.indexOf('only necessary')>=0 || t.indexOf('only essential')>=0 ||
          t.indexOf('deny')>=0 || t.indexOf('refuse')>=0) {
        try { b.click(); } catch(e){}
      }
    });
  }
  // MutationObserver for late-loading banners
  var obs = new MutationObserver(function(){ hide(); });
  if (document.body) { obs.observe(document.body, {childList:true, subtree:true}); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function(){ hide(); obs.observe(document.body||document.documentElement, {childList:true, subtree:true}); });
  } else { hide(); }
  setTimeout(hide, 300);
  setTimeout(hide, 1000);
  setTimeout(hide, 3000);
  setTimeout(function(){ obs.disconnect(); }, 10000);
})();
