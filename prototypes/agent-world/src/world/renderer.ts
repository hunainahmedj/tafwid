import * as THREE from "three/webgpu";
import {
  builtinAOContext, color, emissive, mix, mrt, normalView, output, pass,
  positionWorldDirection, screenUV, smoothstep, uniform, vec4,
} from "three/tsl";
import { ao } from "three/addons/tsl/display/GTAONode.js";
import { bloom } from "three/addons/tsl/display/BloomNode.js";
import { dof } from "three/addons/tsl/display/DepthOfFieldNode.js";
import type { Ambience, EnvironmentManifest } from "../contract/manifest";
import type { Tier } from "../app/types";
import { TIERS } from "./tiers";

export interface WorldRenderer {
  renderer: THREE.WebGPURenderer;
  backend: "webgpu" | "webgl";
  setTier(tier: Tier): void;
  setEnvironment(manifest: EnvironmentManifest): void;
  /** Distance from the camera to the in-focus plane (the camera target). */
  setFocus(distance: number): void;
  render(): void;
  resize(width: number, height: number): void;
  dispose(): void;
}

/**
 * Owns the renderer, lights and post stack. The scene pass writes colour and
 * emissive so bloom only picks up light sources; ambient occlusion feeds
 * back into lighting; depth of field blurs away from the camera target.
 */
export async function createRenderer(
  canvas: HTMLCanvasElement,
  scene: THREE.Scene,
  camera: THREE.PerspectiveCamera,
  initialTier: Tier,
  forceWebGL = false,
): Promise<WorldRenderer> {
  const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, forceWebGL });
  await renderer.init();
  const backend = (renderer.backend as { isWebGPUBackend?: boolean }).isWebGPUBackend ? "webgpu" : "webgl";
  renderer.toneMapping = THREE.AgXToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const hemi = new THREE.HemisphereLight("#ffffff", "#888888", 1);
  const sun = new THREE.DirectionalLight("#ffffff", 3);
  sun.castShadow = true;
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.02;
  scene.add(hemi, sun, sun.target);

  const focus = uniform(30);
  const focalRange = uniform(12);
  const bokeh = uniform(1);
  const bloomStrength = uniform(0.5);
  let tier = initialTier;
  let manifest: EnvironmentManifest | null = null;
  let pipeline: THREE.RenderPipeline | null = null;

  function buildPipeline() {
    pipeline?.dispose();
    const cfg = TIERS[tier];
    const p = new THREE.RenderPipeline(renderer);
    const realtime = manifest?.lighting !== "baked";
    const scenePass = pass(scene, camera, { samples: cfg.samples });
    scenePass.setMRT(mrt({ output, emissive }));
    if (cfg.ao && realtime) {
      const prePass = pass(scene, camera, { samples: 0 });
      prePass.setMRT(mrt({ output: normalView }));
      const aoPass = ao(prePass.getTextureNode("depth"), prePass.getTextureNode(), camera);
      aoPass.resolutionScale = 0.5;
      scenePass.contextNode = builtinAOContext(aoPass.getTextureNode().sample(screenUV).r);
    }
    let result: any = scenePass.getTextureNode("output");
    if (cfg.bloom) {
      const b = bloom(scenePass.getTextureNode("emissive"), 1, manifest?.ambience.bloom.radius ?? 0.4, 0);
      b.strength = bloomStrength;
      result = result.add(b);
    }
    if (cfg.dof) result = dof(result, scenePass.getViewZNode(), focus, focalRange, bokeh);
    // Gentle vignette for the miniature feel.
    const v = smoothstep(0.95, 0.35, screenUV.sub(0.5).length());
    p.outputNode = vec4(result.rgb.mul(mix(0.78, 1.0, v)), 1);
    pipeline = p;
  }

  function applyAmbience(a: Ambience) {
    hemi.color.set(a.hemisphere.sky);
    hemi.groundColor.set(a.hemisphere.ground);
    hemi.intensity = a.hemisphere.intensity;
    sun.color.set(a.sun.color);
    sun.intensity = a.sun.intensity;
    renderer.toneMappingExposure = a.exposure;
    scene.fog = new THREE.Fog(a.fog.color, a.fog.near, a.fog.far);
    scene.backgroundNode = mix(
      color(a.sky.bottom),
      color(a.sky.top),
      smoothstep(-0.05, 0.5, positionWorldDirection.y),
    );
    focalRange.value = a.dof.range;
    bokeh.value = a.dof.strength;
    bloomStrength.value = a.bloom.strength;
  }

  function fitShadow(m: EnvironmentManifest) {
    const b = m.camera.bounds;
    const cx = (b.minX + b.maxX) / 2, cz = (b.minZ + b.maxZ) / 2;
    const half = Math.max(b.maxX - b.minX, b.maxZ - b.minZ) / 2 + 4;
    const [dx, dy, dz] = m.ambience.sun.direction;
    const len = Math.hypot(dx, dy, dz);
    sun.position.set(cx + (dx / len) * 60, (dy / len) * 60, cz + (dz / len) * 60);
    sun.target.position.set(cx, 0, cz);
    Object.assign(sun.shadow.camera, { left: -half, right: half, top: half, bottom: -half, near: 1, far: 140 });
    sun.shadow.camera.updateProjectionMatrix();
  }

  function applyTier() {
    const cfg = TIERS[tier];
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, cfg.pixelRatio));
    sun.shadow.mapSize.set(cfg.shadowMapSize, cfg.shadowMapSize);
    buildPipeline();
  }

  applyTier();

  return {
    renderer,
    backend,
    setTier(t) {
      if (t === tier) return;
      tier = t;
      applyTier();
    },
    setEnvironment(m) {
      manifest = m;
      applyAmbience(m.ambience);
      fitShadow(m);
      // Baked packages carry their lighting; the sun only lights characters and casts no world shadows.
      sun.castShadow = m.lighting !== "baked";
      buildPipeline();
    },
    setFocus(distance) {
      focus.value = distance + (manifest?.ambience.dof.focusOffset ?? 0);
    },
    render() {
      pipeline?.render();
    },
    resize(w, h) {
      renderer.setSize(w, h, false);
      camera.aspect = w / Math.max(1, h);
      camera.updateProjectionMatrix();
    },
    dispose() {
      pipeline?.dispose();
      renderer.dispose();
    },
  };
}

