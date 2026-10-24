var __defProp = Object.defineProperty;
var __defProps = Object.defineProperties;
var __getOwnPropDescs = Object.getOwnPropertyDescriptors;
var __getOwnPropSymbols = Object.getOwnPropertySymbols;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __propIsEnum = Object.prototype.propertyIsEnumerable;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __spreadValues = (a, b) => {
  for (var prop in b || (b = {}))
    if (__hasOwnProp.call(b, prop))
      __defNormalProp(a, prop, b[prop]);
  if (__getOwnPropSymbols)
    for (var prop of __getOwnPropSymbols(b)) {
      if (__propIsEnum.call(b, prop))
        __defNormalProp(a, prop, b[prop]);
    }
  return a;
};
var __spreadProps = (a, b) => __defProps(a, __getOwnPropDescs(b));
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let location = null, pending = null, legacy = null, generation = 0, previewToken = 0, timer, api, changed;
  const note = (text) => {
    $("location-status").textContent = text;
  };
  function read(validate = true) {
    if (validate && pending) throw new Error("正在获取起卦地点，请稍等或手动填写经度。");
    if (legacy) return __spreadValues({}, legacy);
    const raw = $("cast-longitude").value.trim(), result = { time_basis: "true_solar" };
    if (raw) {
      const longitude = Number(raw);
      if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180) throw new Error("经度应在 −180 至 180 之间，东经为正，西经为负。");
      result.cast_location = location && location.longitude === longitude ? __spreadValues({}, location) : { longitude, source: "manual" };
    }
    if (validate && $("cast-time").value && !result.cast_location) throw new Error("请选择定位或手动填写起卦地点的经度。");
    return result;
  }
  function update() {
    $("solar-location-fields").hidden = false;
    clearTimeout(timer);
    const token = ++previewToken;
    $("solar-time-preview").textContent = "";
    if (legacy) {
      $("solar-time-preview").textContent = "该历史记录保留原排盘口径；填写原起卦地点后，可按真太阳时重新排盘。";
      return;
    }
    timer = setTimeout(async () => {
      if (!api || !$("cast-time").value) return;
      try {
        const details = read(false);
        if (details.time_basis === "true_solar" && !details.cast_location) return;
        const date = new Date($("cast-time").value);
        if (Number.isNaN(date.valueOf())) return;
        const value = await api("/api/calendar", { method: "POST", data: __spreadProps(__spreadValues({}, details), { actual_cast_time: date.toISOString() }) });
        if (token !== previewToken) return;
        $("solar-time-preview").textContent = value.status === "computed" ? "当地真太阳时：".concat(value.cast_time.slice(0, 19).replace("T", " ")) : value.message;
      } catch (error) {
        if (token === previewToken) $("solar-time-preview").textContent = error.message;
      }
    }, 250);
  }
  async function locate() {
    if (pending) return;
    const epoch = generation, id = "location_" + Date.now();
    $("location-button").disabled = true;
    note("正在获取起卦地点…");
    try {
      const value = await new Promise((resolve, reject) => {
        var _a;
        const timeout = setTimeout(() => {
          if ((pending == null ? void 0 : pending.id) === id) {
            pending = null;
            reject(new Error("定位未完成，可以重试或手动填写经度。"));
          }
        }, 35e3);
        pending = { id, resolve: (value2) => {
          clearTimeout(timeout);
          resolve(value2);
        }, reject: (error) => {
          clearTimeout(timeout);
          reject(error);
        } };
        if ((_a = window.LiuyaoAndroid) == null ? void 0 : _a.requestLocation) window.LiuyaoAndroid.requestLocation(id);
        else if (navigator.geolocation) navigator.geolocation.getCurrentPosition((position) => receive(id, {
          longitude: position.coords.longitude,
          latitude: position.coords.latitude,
          accuracy_m: position.coords.accuracy,
          captured_at: new Date(position.timestamp).toISOString(),
          source: "device"
        }), () => receive(id, { error: "未能获取定位，请检查定位权限，或手动填写经度。" }), { enableHighAccuracy: true, timeout: 2e4, maximumAge: 0 });
        else receive(id, { error: "当前环境无法定位，请手动填写起卦地点的经度。" });
      });
      if (epoch !== generation) return;
      legacy = null;
      location = value;
      $("cast-longitude").value = String(value.longitude);
      note("已定位：".concat(value.longitude.toFixed(5), "°").concat(value.latitude !== void 0 ? "，".concat(value.latitude.toFixed(5), "°") : "").concat(value.accuracy_m !== void 0 ? "；精度约 ".concat(Math.round(value.accuracy_m), " 米") : "", "。补录旧卦请填写当时地点。"));
      update();
      changed();
    } catch (error) {
      if (epoch === generation) note(error.message);
    } finally {
      if (epoch === generation) {
        pending = null;
        $("location-button").disabled = false;
      }
    }
  }
  function receive(id, value) {
    if ((pending == null ? void 0 : pending.id) !== id) return;
    const request = pending;
    pending = null;
    if (value == null ? void 0 : value.error) request.reject(new Error(value.error));
    else request.resolve(value);
  }
  function fill(input) {
    generation++;
    if (pending) {
      pending.reject(new Error("已切换案例。"));
      pending = null;
    }
    location = (input == null ? void 0 : input.cast_location) ? __spreadValues({}, input.cast_location) : null;
    legacy = input && (input.time_basis || "beijing_standard") !== "true_solar" ? __spreadValues(__spreadValues({}, input.time_basis ? { time_basis: input.time_basis } : {}), location ? { cast_location: __spreadValues({}, location) } : {}) : null;
    $("cast-longitude").value = location ? String(location.longitude) : "";
    $("location-button").disabled = false;
    note(location ? "已保存起卦地点；可手动更正经度。" : "定位仅在起卦时获取；补录旧卦请填写当时地点。");
    update();
  }
  window.LiuyaoLocation = { receive };
  function useCurrentTime() {
    legacy = null;
    update();
    changed();
    locate();
  }
  function timeChanged() {
    legacy = null;
    update();
    changed();
    if ($("cast-time").value && !$("cast-longitude").value) locate();
  }
  function clearTime() {
    generation++;
    if (pending) {
      pending.reject(new Error("已清空起卦时间。"));
      pending = null;
    }
    legacy = null;
    $("location-button").disabled = false;
    update();
  }
  window.LiuyaoSolarTime = { read, fill, update, locate, useCurrentTime, clearTime, bind(options) {
    api = options.api;
    changed = options.changed;
    $("location-button").addEventListener("click", locate);
    $("cast-longitude").addEventListener("input", () => {
      generation++;
      if (pending) {
        pending.reject(new Error("已改用手动经度。"));
        pending = null;
      }
      legacy = null;
      location = null;
      $("location-button").disabled = false;
      note("使用手动填写的起卦地点。");
      update();
      changed();
    });
    $("cast-time").addEventListener("change", timeChanged);
    fill(null);
  } };
})();
