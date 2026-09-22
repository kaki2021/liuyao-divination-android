(function() {
  "use strict";
  function install(target, name, value) {
    if (!target[name]) Object.defineProperty(target, name, { value, configurable: true, writable: true });
  }
  function replaceChildren() {
    var fragment = document.createDocumentFragment();
    for (var i = 0; i < arguments.length; i++) {
      var child = arguments[i];
      fragment.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    while (this.firstChild) this.removeChild(this.firstChild);
    this.appendChild(fragment);
  }
  [Element.prototype, DocumentFragment.prototype, Document.prototype].forEach(function(prototype) {
    install(prototype, "replaceChildren", replaceChildren);
  });
  install(Array.prototype, "at", function(index) {
    var i = Math.trunc(Number(index) || 0);
    if (i < 0) i += this.length;
    return this[i];
  });
  install(Object, "hasOwn", function(object, key) {
    return Object.prototype.hasOwnProperty.call(object, key);
  });
  install(Object, "fromEntries", function(entries) {
    var result = {};
    Array.from(entries).forEach(function(entry) {
      Object.defineProperty(result, entry[0], { value: entry[1], enumerable: true, configurable: true, writable: true });
    });
    return result;
  });
  install(Promise, "allSettled", function(values) {
    return Promise.all(Array.from(values).map(function(value) {
      return Promise.resolve(value).then(
        function(result) {
          return { status: "fulfilled", value: result };
        },
        function(error) {
          return { status: "rejected", reason: error };
        }
      );
    }));
  });
  install(Blob.prototype, "arrayBuffer", function() {
    var blob = this;
    return new Promise(function(resolve, reject) {
      var reader = new FileReader();
      reader.onload = function() {
        resolve(reader.result);
      };
      reader.onerror = function() {
        reject(reader.error || new Error("文件读取失败，请重新选择。"));
      };
      reader.readAsArrayBuffer(blob);
    });
  });
  function requestId() {
    var bytes = window.crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = bytes[6] & 15 | 64;
    bytes[8] = bytes[8] & 63 | 128;
    var hex = Array.from(bytes, function(b) {
      return ("0" + b.toString(16)).slice(-2);
    }).join("");
    return hex.slice(0, 8) + "-" + hex.slice(8, 12) + "-" + hex.slice(12, 16) + "-" + hex.slice(16, 20) + "-" + hex.slice(20);
  }
  window.LiuyaoCompat = { requestId };
  function startupFailure() {
    var banner = document.getElementById("global-message");
    if (banner) {
      banner.textContent = "页面未能完整加载，请关闭应用后重新打开。已保存的案例仍保留。";
      banner.className = "message-banner error";
      banner.hidden = false;
    }
  }
  window.addEventListener("error", function() {
    if (!window.LiuyaoApp) startupFailure();
  });
  document.addEventListener("submit", function(event) {
    if (event.target.getAttribute("method") !== "dialog") {
      event.preventDefault();
      if (!window.LiuyaoApp) startupFailure();
    }
  }, true);
})();
