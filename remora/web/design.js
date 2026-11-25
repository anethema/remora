"use strict";

const boatDesign = (() => {
  const get = id => document.getElementById(id);
  const presets = {
    light: [3.0, 150], standard: [3.7, 200], loaded: [4.3, 250],
  };
  const defaults = {
    model: "native", length_m: 3.7, mass_kg: 200, thrust_lbf: 55, max_current_a: 50,
    steering: "steerable", battery: "LiFePO4", capacity_ah: 100, wind_speed_mps: 0,
    wind_from_deg: 0, wind_cda_bow_m2: 0.7, wind_cda_beam_m2: 2.0, current_e_mps: 0, current_n_mps: 0,
  };
  const methods = {
    steerable: "Single steerable motor", rudder: "Fixed motor and rudder", differential: "Twin differential thrust",
  };
  function update() {
    get("hull-controls").disabled = get("boat-model").value === "native";
    get("native-note").hidden = get("boat-model").value !== "native";
    const thrust = Number(get("thrust_lbf").value);
    const motors = get("steering").value === "differential" ? 2 : 1;
    get("thrust-value").textContent = Number.isFinite(thrust) ?
      Math.round(thrust * 4.44822) + " N per motor · " + motors + (motors === 1 ? " motor" : " motors") : "";
    const d = Number(get("wind_from_deg").value);
    get("wind-value").textContent = Number.isFinite(d) ?
      "Blows toward " + Math.round((d + 180) % 360) + "° true" : "";
  }
  function fill(scenario) {
    const d = {...defaults, ...scenario.boat_design};
    get("authorization").value = scenario.authorization || "surface_operator";
    get("boat-model").value = d.model;
    for (const key of Object.keys(defaults)) {
      if (key === "model") continue;
      get(key).value = key === "wind_speed_mps" ? +(d[key]*3.6).toFixed(4) : d[key];
    }
    get("hull-preset").value = Object.keys(presets).find(k => presets[k][0] === d.length_m && presets[k][1] === d.mass_kg) || "custom";
    update();
  }
  function read() {
    const d = {model:get("boat-model").value};
    for (const key of Object.keys(defaults)) {
      if (key === "model") continue;
      const control = get(key);
      d[key] = control.type === "number" ? control.valueAsNumber : control.value;
    }
    d.wind_speed_mps /= 3.6;
    return {boat_design:d, authorization:get("authorization").value};
  }
  get("hull-preset").onchange = () => {
    const preset = presets[get("hull-preset").value];
    if (preset) [get("length_m").value, get("mass_kg").value] = preset;
  };
  for (const id of ["length_m","mass_kg"]) get(id).oninput = () => {get("hull-preset").value = "custom";};
  for (const id of ["boat-model","steering","thrust_lbf","wind_from_deg"]) get(id).addEventListener("input",update);
  function summary(s) {
    const d=s.boat_design;
    if (!d || d.model === "native") return "Native motorboat · fixed reference model · calm water";
    return d.length_m+" m · "+d.mass_kg+" kg · "+d.thrust_lbf+" lbf per motor · "+ methods[d.steering]+
      " · Wind "+(d.wind_speed_mps*3.6).toFixed(1)+" km/h from "+d.wind_from_deg+"°";
  }
  return {fill,read,summary};
})();
