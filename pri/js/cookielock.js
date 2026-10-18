
(function(){
  try {
    Object.defineProperty(navigator, 'cookieEnabled', {get: function(){return false;}, configurable:true});
  } catch(e){}
  try {
    var d = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie');
    if (d && d.set) {
      Object.defineProperty(document, 'cookie', {
        configurable: true,
        get: function(){ return d.get ? d.get.call(this) : ''; },
        set: function(){ /* blocked by Pri */ }
      });
    }
  } catch(e){}
})();
